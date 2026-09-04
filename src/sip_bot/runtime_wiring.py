"""Procedural live-call wiring for the one-call asyncio runtime.

This module contains no dialogue, lifecycle, media, speech, or delivery
ownership.  It only materializes the already accepted typed boundaries:
PJSUA2/PJMEDIA polling, the specialised PCM fan-out, the ASR worker bridge,
the existing speech/conversation owners, and paced playback.  The only
cross-thread queues here are bounded ``queue.Queue`` instances.  The module
does not create an asyncio queue because the payload boundaries are between
the main asyncio thread and worker threads.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from time import monotonic_ns
from typing import Any

from .config import RuntimeConfig
from .conversation_pipeline import ConversationPipeline
from .dialogue.actions import CommandKind, DialogueCommand
from .dialogue.events import (
    PlaybackEvent as DialoguePlaybackEvent,
    PlaybackStatus,
    SpeechEvent,
    SpeechEventKind,
)
from .media import AsrChunker, PcmFanOut, PcmFanOutSubscription
from .playback import PlaybackChannel, PlaybackEventKind
from .runtime_composition import CallComposition
from .sip_media.models import NegotiatedMediaProfile, PcmFrame
from .sip_media.media_port import EgressSourceMode
from .sip_media.protocol_events import NormalizedSipEvent
from .speech import AsrAudioChunk, AsrHypothesis, EndpointEvent, EndpointEventKind, SpeechIngress, StreamingAsrAdapter
from .tts import MediaPacer, TtsOutputBuffer, TtsPcmChunk


@dataclass(slots=True)
class RuntimeWiringStats:
    sip_polls: int = 0
    control_dispatches: int = 0
    ingress_frames: int = 0
    fanout_frames: int = 0
    asr_chunks_queued: int = 0
    asr_chunks_dropped: int = 0
    asr_hypotheses: int = 0
    final_turns: int = 0
    tts_chunks: int = 0
    tts_frames_sent: int = 0
    stale_hypotheses: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {name: int(getattr(self, name)) for name in self.__dataclass_fields__}


class RuntimeWiringError(RuntimeError):
    """Raised when a required existing boundary is not available."""


class CallRuntimeWiring:
    """Materialize one call's existing boundaries on the main asyncio loop."""

    def __init__(
        self,
        composition: CallComposition,
        *,
        sip_media: Any,
        speech: SpeechIngress,
        asr: StreamingAsrAdapter,
        pipeline: ConversationPipeline | Any,
        config: RuntimeConfig | None = None,
        clock_ns: Callable[[], int] = monotonic_ns,
    ) -> None:
        if not isinstance(composition, CallComposition):
            raise TypeError("runtime wiring requires CallComposition")
        if not isinstance(speech, SpeechIngress):
            raise TypeError("runtime wiring requires SpeechIngress")
        if not isinstance(asr, StreamingAsrAdapter):
            raise TypeError("runtime wiring requires StreamingAsrAdapter")
        for name in ("poll", "dispatch_events", "next_ingress_frame", "enqueue_egress_frame"):
            if not callable(getattr(sip_media, name, None)):
                raise TypeError(f"sip_media must provide {name}()")
        for name in ("submit_final_turn", "drain_control"):
            if not callable(getattr(pipeline, name, None)):
                raise TypeError(f"pipeline must provide {name}()")
        self.composition = composition
        self.sip_media = sip_media
        self.speech = speech
        self.asr = asr
        self.pipeline = pipeline
        self.config = config or RuntimeConfig.from_constants()
        self.clock_ns = clock_ns
        self.stats = RuntimeWiringStats()
        self.errors: list[str] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = Event()
        self._started = False
        self._asr_thread: Thread | None = None
        self._asr_operation: Any | None = None
        self._asr_input: Queue[AsrAudioChunk] = Queue(maxsize=self.config.audio_input_buffer_capacity_frames)
        self._asr_output: Queue[AsrHypothesis] = Queue(maxsize=self.config.audio_input_buffer_capacity_frames)
        self._asr_errors: Queue[BaseException] = Queue(maxsize=8)
        self._fanout: PcmFanOut | None = None
        self._vad_input: PcmFanOutSubscription | None = None
        self._asr_input_subscription: PcmFanOutSubscription | None = None
        self._chunker: AsrChunker | None = None
        self._speech_frame_sequences: set[int] = set()
        self._playback_lock = Lock()
        self._outputs: dict[tuple[str, int], TtsOutputBuffer] = {}
        self._playback: dict[tuple[str, int], PlaybackChannel] = {}
        self._pending_physical_close: set[tuple[str, int]] = set()
        self._speech_event_sequence = 0
        self._previous_audio_sink = getattr(pipeline, "audio_sink", None)
        self._bind_existing_boundaries()

    @property
    def started(self) -> bool:
        return self._started

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    @property
    def fanout(self) -> PcmFanOut | None:
        return self._fanout

    @property
    def asr_input_queue_capacity(self) -> int:
        return self._asr_input.maxsize

    def tts_output_stats(self) -> dict[str, int]:
        """Return observable accounting for all playback generations.

        The payload remains on the direct TTS/playback data plane.  This
        snapshot is diagnostic evidence only; it is not a control-plane
        message and does not participate in playback scheduling.
        """

        with self._playback_lock:
            outputs = tuple(self._outputs.values())
        names = (
            "accepted_chunks",
            "accepted_bytes",
            "emitted_frames",
            "emitted_bytes",
            "flushed_tail_frames",
            "dropped_tail_bytes",
            "dropped_stale_chunks",
            "dropped_closed_chunks",
            "dropped_cancelled_chunks",
            "dropped_overflow_bytes",
        )
        result = {name: sum(int(getattr(output.stats, name)) for output in outputs) for name in names}
        result["buffered_bytes"] = sum(output.buffered_bytes for output in outputs)
        result["pending_frames"] = sum(output.pending_frames for output in outputs)
        return result

    def _bind_existing_boundaries(self) -> None:
        # SIP control is delivered to the existing Dispatcher queue.  The
        # adapter's native callbacks still only enqueue compact events.
        if hasattr(self.sip_media, "event_sink"):
            self.sip_media.event_sink = self.composition.dispatcher
        self.composition.add_command_observer(self._on_command)
        self.composition.add_control_observer(self._on_control_submitted)
        if hasattr(self.pipeline, "audio_sink"):
            self.pipeline.audio_sink = self._on_tts_chunk

    def start(self) -> None:
        if self._started:
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeWiringError("CallRuntimeWiring.start() must run in the main asyncio loop") from exc
        self._stop.clear()
        self._started = True
        self._asr_thread = Thread(target=self._asr_worker, name="sip-bot-asr-boundary", daemon=True)
        self._asr_thread.start()

    async def run(self, *, interval_s: float = 0.01) -> None:
        """Run the non-blocking main-loop driver until ``stop`` is called."""

        if interval_s < 0:
            raise ValueError("interval_s must not be negative")
        self.start()
        while not self._stop.is_set():
            await self.step()
            if interval_s:
                await asyncio.sleep(interval_s)

    async def step(self, *, now_ns: int | None = None) -> RuntimeWiringStats:
        """Run one bounded main-loop turn without waiting for inference."""

        if not self._started:
            self.start()
        self.sip_media.poll(0)
        self.stats.sip_polls += 1
        self.stats.control_dispatches += int(self.sip_media.dispatch_events())
        # Apply protocol/control events before consuming the corresponding
        # media frame.  A CALL_ANSWERED event must open the speech channel
        # before a same-tick ingress frame can produce a user turn.
        self._drain_control()
        self._drain_asr_results()
        self._drain_media_ingress()
        # Endpoint lifecycle events must be applied before a worker result can
        # deliver the corresponding authoritative FinalUserTurn.  Otherwise
        # a queued SPEECH_STARTED from this same media burst could be drained
        # after the direct turn delivery and cancel the newly started
        # inference as if it were a later speech resumption.
        self._drain_control()
        self._flush_chunker_timer(now_ns)
        self._drain_asr_results()
        self._drain_control()
        self._pump_playback(now_ns)
        await asyncio.sleep(0)
        return self.stats

    def _drain_control(self) -> int:
        """Drain the existing pipeline/Dispatcher control boundary."""

        processed = int(self.pipeline.drain_control())
        if processed == 0:
            # Test doubles and lightweight pipeline facades may expose the
            # required method without owning the Dispatcher drain.  The
            # existing composition remains the authoritative control owner.
            processed += self.composition.drain_control()
        self.stats.control_dispatches += processed
        return processed

    def stop(self, reason: str = "runtime_wiring_stop") -> None:
        if not self._started:
            return
        self._stop.set()
        if self._chunker is not None:
            self._chunker.cancel()
        self.asr.close()
        self.speech.close()
        self.pipeline.close(reason) if callable(getattr(self.pipeline, "close", None)) else None
        worker = self._asr_thread
        if worker is not None:
            worker.join(timeout=1.0)
        self._asr_thread = None
        self._speech_frame_sequences.clear()
        self._started = False

    def _drain_media_ingress(self) -> None:
        while True:
            frame = self.sip_media.next_ingress_frame()
            if frame is None:
                return
            if not isinstance(frame, PcmFrame):
                self._record_error(TypeError("SipMediaAdapter returned an untyped PcmFrame"))
                continue
            self.stats.ingress_frames += 1
            self._ensure_media_boundaries(frame)
            assert self._fanout is not None
            result = self._fanout.publish(frame)
            self.stats.fanout_frames += len(result.delivered_to)
            self._drain_vad()
            self._drain_asr_audio()

    def _ensure_media_boundaries(self, frame: PcmFrame) -> None:
        if self._fanout is not None:
            if frame.generation != self._fanout.generation:
                raise RuntimeWiringError("media generation changed; a fresh per-generation SpeechIngress is required")
            return
        self._fanout = PcmFanOut(
            capacity_frames=self.config.audio_input_buffer_capacity_frames,
            generation=frame.generation,
        )
        self._vad_input = self._fanout.subscribe("vad")
        self._asr_input_subscription = self._fanout.subscribe("asr_input_accumulator")
        self._chunker = AsrChunker(
            profile=frame.profile,
            call_id=frame.call_id,
            channel_id=frame.channel_id,
            generation=frame.generation,
            chunk_ms=self.config.asr_chunk_ms,
            flush_ms=self.config.asr_chunk_flush_ms,
            max_pending_chunks=self.config.audio_input_buffer_capacity_frames,
            clock_ns=self.clock_ns,
        )
        self._asr_operation = self.asr.open_operation(
            call_id=frame.call_id,
            channel_id=frame.channel_id,
            generation=frame.generation,
        )

    def _drain_vad(self) -> None:
        if self._vad_input is None:
            return
        for frame in self._drain_subscription(self._vad_input):
            result = self.speech.process_frame(frame)
            if result.vad_decision.is_speech:
                self._speech_frame_sequences.add(frame.sequence)
            self._publish_speech_events(result.endpoint_events)
            if (
                self.speech.defer_endpoint_finalization
                and any(event.kind is EndpointEventKind.HARD_ENDPOINT for event in result.endpoint_events)
                and self._chunker is not None
            ):
                # The hard-endpoint chunk is the ASR-side commit marker.  It
                # is queued after all target chunks already accumulated for
                # this turn, so the assembler waits for the most complete
                # revision instead of finalizing on a late earlier chunk.
                self._queue_ready_chunks(self._chunker.hard_endpoint())
            if result.final_turn is not None:
                self.stats.final_turns += 1
                if not self.pipeline.submit_final_turn(result.final_turn):
                    self._record_error(RuntimeWiringError("ConversationPipeline rejected FinalUserTurn"))

    def _publish_speech_events(self, events: tuple[EndpointEvent, ...]) -> None:
        """Materialize speech lifecycle outputs on the existing control edge.

        ``SpeechIngress`` owns VAD/endpointing and returns typed endpoint data;
        the runtime only adapts that output to the already accepted compact
        FSM control event.  A speech start/resume while playback is active is
        explicitly classified as ``barge_in`` so the FSM closes playback
        before the next authoritative turn is accepted.
        """

        for event in events:
            self._speech_event_sequence += 1
            kind = _speech_event_kind(event.kind)
            if (
                event.kind in {EndpointEventKind.SPEECH_STARTED, EndpointEventKind.SPEECH_RESUMED}
                and self.composition.fsm.state.value in {"playing", "offering_transfer"}
            ):
                kind = SpeechEventKind.BARGE_IN
            accepted = self.composition.submit_control(
                SpeechEvent(
                    event.call_id,
                    kind,
                    sequence=self._speech_event_sequence,
                    channel_id=event.channel_id,
                    channel_generation=event.generation,
                    reason=event.reason,
                )
            )
            if not accepted:
                self._record_error(RuntimeWiringError("Dispatcher rejected SpeechEvent"))

    def _drain_asr_audio(self) -> None:
        if self._asr_input_subscription is None or self._chunker is None:
            return
        for frame in self._drain_subscription(self._asr_input_subscription):
            if frame.sequence not in self._speech_frame_sequences:
                continue
            self._speech_frame_sequences.discard(frame.sequence)
            self._queue_ready_chunks(self._chunker.push(frame))

    @staticmethod
    def _drain_subscription(subscription: PcmFanOutSubscription) -> tuple[PcmFrame, ...]:
        values: list[PcmFrame] = []
        while True:
            frame = subscription.get_nowait()
            if frame is None:
                return tuple(values)
            values.append(frame)

    def _queue_ready_chunks(self, _emitted_count: int) -> None:
        if self._chunker is None:
            return
        while True:
            chunk = self._chunker.next_chunk()
            if chunk is None:
                return
            try:
                self._asr_input.put_nowait(chunk)
            except Full:
                self.stats.asr_chunks_dropped += 1
                self._record_error(RuntimeWiringError("bounded ASR worker queue overflow"))
            else:
                self.stats.asr_chunks_queued += 1

    def _flush_chunker_timer(self, now_ns: int | None) -> None:
        if self._chunker is not None:
            self._queue_ready_chunks(self._chunker.on_timer(now_ns))

    def _asr_worker(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._asr_input.get(timeout=0.02)
            except Empty:
                continue
            operation = self._asr_operation
            if operation is None:
                continue
            try:
                for hypothesis in self.asr.stream(operation, (chunk,)):
                    try:
                        self._asr_output.put_nowait(hypothesis)
                    except Full:
                        self._record_error(RuntimeWiringError("bounded ASR result queue overflow"))
            except BaseException as exc:
                try:
                    self._asr_errors.put_nowait(exc)
                except Full:
                    pass

    def _drain_asr_results(self) -> None:
        while True:
            try:
                error = self._asr_errors.get_nowait()
            except Empty:
                break
            self._record_error(error)
        while True:
            try:
                hypothesis = self._asr_output.get_nowait()
            except Empty:
                return
            self.stats.asr_hypotheses += 1
            if self.speech.accept_hypothesis(hypothesis) is None:
                self.stats.stale_hypotheses += 1
            final_turn = self.speech.take_final_turn()
            if final_turn is not None:
                self.stats.final_turns += 1
                if not self.pipeline.submit_final_turn(final_turn):
                    self._record_error(RuntimeWiringError("ConversationPipeline rejected FinalUserTurn"))

    def _on_command(self, command: DialogueCommand) -> None:
        if command.call_id != self.composition.session.call_id:
            return
        try:
            if command.kind is CommandKind.ANSWER:
                self.sip_media.answer()
            elif command.kind is CommandKind.HANGUP:
                self.sip_media.hangup(command.reason or "dialogue_hangup")
            elif command.kind is CommandKind.TRANSFER:
                if not command.target:
                    raise RuntimeWiringError("transfer command has no target")
                self.sip_media.transfer(command.target)
            elif command.kind is CommandKind.CANCEL and command.channel_id == "playback":
                self._cancel_playback(command.channel_id, command.generation, command.reason or "cancelled")
            elif command.kind is CommandKind.CLOSE_CHANNEL and command.channel_id == "playback":
                self._close_playback(command.channel_id, command.generation, command.reason or "closed")
        except BaseException as exc:
            self._record_error(exc)

    def _on_control_submitted(self, event: object, accepted: bool) -> None:
        if not accepted or not isinstance(event, DialoguePlaybackEvent):
            return
        if event.status is PlaybackStatus.COMPLETED:
            key = (event.channel_id, event.channel_generation or 0)
            with self._playback_lock:
                output = self._outputs.get(key)
                if output is not None:
                    output.complete()
                self._pending_physical_close.add(key)

    def _on_tts_chunk(self, chunk: TtsPcmChunk) -> None:
        if self._previous_audio_sink is not None:
            self._previous_audio_sink(chunk)
        if not isinstance(chunk, TtsPcmChunk):
            self._record_error(TypeError("TTS sink received an untyped chunk"))
            return
        key = (chunk.channel_id, chunk.generation)
        with self._playback_lock:
            output = self._outputs.get(key)
            if output is None:
                output = TtsOutputBuffer(
                    profile=chunk.profile,
                    call_id=chunk.call_id,
                    channel_id=chunk.channel_id,
                    generation=chunk.generation,
                    start_timestamp_ns=self.clock_ns(),
                )
                channel = PlaybackChannel(
                    call_id=chunk.call_id,
                    channel_id=chunk.channel_id,
                    generation=chunk.generation,
                    pacer=MediaPacer(output, clock_ns=self.clock_ns),
                    send_frame=self.sip_media.enqueue_egress_frame,
                    on_event=self._on_playback_event,
                    clock_ns=self.clock_ns,
                )
                channel.open()
                self._outputs[key] = output
                self._playback[key] = channel
            accepted = output.push(chunk)
            self.stats.tts_chunks += 1
        # Do not move a stale/closed generation back into PREROLL.  Source
        # selection follows the accepted typed payload, not mere arrival of
        # a producer callback.
        if accepted:
            self._set_egress_source_mode(EgressSourceMode.PREROLL)

    def _on_playback_event(self, event: Any) -> None:
        if event.kind is PlaybackEventKind.STARTED:
            self._set_egress_source_mode(EgressSourceMode.PLAYING)
            status = PlaybackStatus.STARTED
        elif event.kind is PlaybackEventKind.FAILED:
            self._set_egress_source_mode(EgressSourceMode.CANCELLED)
            status = PlaybackStatus.FAILED
        elif event.kind is PlaybackEventKind.CANCELLED:
            self._set_egress_source_mode(EgressSourceMode.CANCELLED)
            status = PlaybackStatus.CANCELLED
        else:
            return
        self.composition.submit_control(
            DialoguePlaybackEvent(
                event.call_id,
                status,
                channel_id=event.channel_id,
                channel_generation=event.generation,
                reason=event.reason or None,
            )
        )

    def _pump_playback(self, now_ns: int | None) -> None:
        with self._playback_lock:
            channels = tuple(self._playback.items())
        for key, channel in channels:
            active_call_id = getattr(self.sip_media, "active_call_id", channel.call_id)
            if active_call_id != channel.call_id:
                # SIP teardown can race with the next main-loop tick.  The
                # playback channel is stale at this point; close it locally
                # instead of calling a media bridge that PJMEDIA has already
                # detached.
                channel.cancel("call_ended")
                with self._playback_lock:
                    self._pending_physical_close.discard(key)
                continue
            try:
                frame = channel.pump(now_ns)
            except BaseException as exc:
                self._record_error(exc)
                continue
            if frame is not None:
                self.stats.tts_frames_sent += 1
            with self._playback_lock:
                output = self._outputs.get(key)
                should_close = key in self._pending_physical_close and output is not None and output.pending_frames == 0
            if should_close:
                self._set_egress_source_mode(EgressSourceMode.DRAINING)
                channel.close("completed")
                self.composition.submit_control(
                    DialoguePlaybackEvent(
                        channel.call_id,
                        PlaybackStatus.COMPLETED,
                        channel_id=channel.channel_id,
                        channel_generation=channel.generation,
                        operation_id=self.composition.fsm.active_operation_id,
                    )
                )
                with self._playback_lock:
                    self._pending_physical_close.discard(key)

    def _cancel_playback(self, channel_id: str | None, generation: int | None, reason: str) -> None:
        if channel_id is None or generation is None:
            return
        with self._playback_lock:
            channel = self._playback.get((channel_id, generation))
        if channel is not None:
            self._set_egress_source_mode(EgressSourceMode.CANCELLED)
            channel.cancel(reason)

    def _close_playback(self, channel_id: str | None, generation: int | None, reason: str) -> None:
        if channel_id is None or generation is None:
            return
        key = (channel_id, generation)
        with self._playback_lock:
            channel = self._playback.get(key)
            output = self._outputs.get(key)
            if channel is None:
                return
            if reason == "completed" and output is not None and output.pending_frames:
                self._pending_physical_close.add(key)
                return
        channel.close(reason)

    def _set_egress_source_mode(self, mode: EgressSourceMode) -> None:
        setter = getattr(self.sip_media, "set_egress_source_mode", None)
        if callable(setter):
            try:
                setter(mode)
            except RuntimeError as exc:
                # Teardown can remove the bridge between the SIP callback and
                # the next main-loop lifecycle event; that is not a playback
                # error once the call is already inactive.
                if getattr(self.sip_media, "active_call_id", None) is not None:
                    self._record_error(exc)

    def _record_error(self, error: BaseException) -> None:
        self.stats.errors += 1
        self.errors.append(f"{type(error).__name__}: {error}")


def _speech_event_kind(kind: EndpointEventKind) -> SpeechEventKind:
    """Map the speech owner's lifecycle enum to the FSM control enum."""

    return SpeechEventKind(kind.value)


__all__ = ["CallRuntimeWiring", "RuntimeWiringError", "RuntimeWiringStats"]
