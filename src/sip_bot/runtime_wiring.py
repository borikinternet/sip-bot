"""Procedural live-call wiring for the one-call asyncio runtime.

This module contains no dialogue, media, speech, or delivery ownership.  Its
optional admission gate owns only the pending incoming-call admission
lifecycle; it does not own dialogue state or model state.  The module
materializes the already accepted typed boundaries:
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
import inspect
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from time import monotonic_ns
from typing import Any

from .config import RuntimeConfig
from .control import SessionLease
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
from .sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from .speech import AsrAudioChunk, AsrHypothesis, EndpointEvent, EndpointEventKind, SpeechIngress, StreamingAsrAdapter
from .tts import MediaPacer, TtsLatencyEvent, TtsLatencySink, TtsLatencyStage, TtsOutputBuffer, TtsPcmChunk
from .understanding import SemanticTurnParser


@dataclass(slots=True)
class RuntimeWiringStats:
    sip_polls: int = 0
    control_dispatches: int = 0
    ingress_frames: int = 0
    fanout_frames: int = 0
    asr_chunks_queued: int = 0
    asr_chunks_dropped: int = 0
    asr_hypotheses: int = 0
    asr_rejected_hypotheses: int = 0
    final_turns: int = 0
    tts_chunks: int = 0
    tts_frames_sent: int = 0
    stale_hypotheses: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {name: int(getattr(self, name)) for name in self.__dataclass_fields__}


class RuntimeWiringError(RuntimeError):
    """Raised when a required existing boundary is not available."""


class _WiringSipEventSink:
    """Object-shaped sink kept compatible with SipMediaAdapter.dispatch_events."""

    def __init__(self, owner: "CallRuntimeWiring") -> None:
        self.owner = owner

    def publish(self, event: NormalizedSipEvent) -> None:
        self.owner._on_sip_event(event)


class IncomingCallReadinessGate:
    """Admit an incoming call only after aggregate runtime readiness.

    The SIP adapter sends the immediate provisional ``180 Ringing`` itself.
    This owner performs only the later application decision on the main
    asyncio loop. Synchronous warmup is moved to a worker thread so the loop
    continues polling SIP and can observe a remote terminal event.
    """

    _TERMINAL_EVENTS = {
        SipEventKind.REMOTE_HANGUP,
        SipEventKind.REMOTE_CANCEL,
        SipEventKind.CALL_ENDED,
        SipEventKind.MEDIA_FAILED,
        SipEventKind.RTP_TIMEOUT,
    }

    def __init__(
        self,
        sip_media: Any,
        *,
        readiness: Any,
        failure_status_code: int = 503,
        call_prepare: Callable[[str, str], object] | None = None,
        call_cleanup: Callable[[str, str], object] | None = None,
        preparation_timeout_s: float = 15.0,
    ) -> None:
        if not callable(getattr(sip_media, "answer", None)):
            raise TypeError("sip_media must provide answer()")
        if not callable(getattr(sip_media, "reject", None)):
            raise TypeError("sip_media must provide reject()")
        if not callable(getattr(readiness, "ensure_ready", None)) or not isinstance(
            getattr(readiness, "ready", None), bool
        ):
            raise TypeError("readiness gate requires a coordinator with bool ready and ensure_ready()")
        if not 300 <= int(failure_status_code) <= 699:
            raise ValueError("failure_status_code must be in the 3xx..6xx range")
        if preparation_timeout_s <= 0:
            raise ValueError("preparation_timeout_s must be positive")
        if call_prepare is not None and not callable(call_prepare):
            raise TypeError("call_prepare must be callable")
        if call_cleanup is not None and not callable(call_cleanup):
            raise TypeError("call_cleanup must be callable")
        self.sip_media = sip_media
        self.readiness = readiness
        self.failure_status_code = int(failure_status_code)
        self.call_prepare = call_prepare
        self.call_cleanup = call_cleanup
        self.preparation_timeout_s = float(preparation_timeout_s)
        self._task: asyncio.Task[None] | None = None
        self._pending_call_id: str | None = None
        self._pending_caller_id: str | None = None
        self._active_call_id: str | None = None
        self._active_caller_id: str | None = None
        self._preparation_tasks: dict[str, asyncio.Task[object]] = {}
        self._cleanup_tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    @property
    def pending_call_id(self) -> str | None:
        return self._pending_call_id

    @property
    def warmup_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def observe(self, event: NormalizedSipEvent) -> None:
        """Observe an already queued SIP event; never run warmup inline."""

        if not isinstance(event, NormalizedSipEvent) or self._closed:
            return
        details = event.details_dict()
        if (
            event.kind is SipEventKind.CALL_STARTED
            and details.get("direction") == "incoming"
            and details.get("answer_pending") is True
        ):
            if self._pending_call_id is not None:
                return
            self._pending_call_id = event.call_id
            self._pending_caller_id = event.caller_id or _caller_id_from_details(details)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError as exc:
                self._pending_call_id = None
                raise RuntimeWiringError("incoming readiness must be observed in the main asyncio loop") from exc
            self._task = loop.create_task(
                self._admit(event.call_id, self._pending_caller_id),
                name=f"sip-bot-admission-{event.call_id}",
            )
            return
        if event.kind in self._TERMINAL_EVENTS:
            if self._pending_call_id == event.call_id:
                caller_id = self._pending_caller_id
                self._cancel_pending()
                self._schedule_cleanup(event.call_id, caller_id)
            elif self._active_call_id == event.call_id:
                caller_id = self._active_caller_id
                self._active_call_id = None
                self._active_caller_id = None
                self._schedule_cleanup(event.call_id, caller_id)

    def close(self) -> None:
        self._closed = True
        pending = (self._pending_call_id, self._pending_caller_id)
        active = (self._active_call_id, self._active_caller_id)
        self._cancel_pending()
        if pending[0] is not None:
            self._schedule_cleanup(*pending)  # type: ignore[arg-type]
        if active[0] is not None:
            self._active_call_id = None
            self._active_caller_id = None
            self._schedule_cleanup(*active)  # type: ignore[arg-type]

    async def _admit(self, call_id: str, caller_id: str | None) -> None:
        prepare_attempted = False
        prepared = False
        try:
            if not self._is_current(call_id):
                return
            if not self.readiness.ready:
                await self.readiness.ensure_ready()
            if not self._is_current(call_id) or not self.readiness.ready:
                return
            if self.call_prepare is not None:
                prepare_attempted = True
                if caller_id is None:
                    raise RuntimeError("incoming call has no caller-id routing key")
                await self._run_hook(self.call_prepare, call_id, caller_id, self.preparation_timeout_s)
                prepared = True
            if not self._is_current(call_id):
                if prepared:
                    self._schedule_cleanup(call_id, caller_id)
                return
            if not self.sip_media.answer():
                raise RuntimeError("SIP adapter did not accept pending call")
            self._active_call_id = call_id
            self._active_caller_id = caller_id
        except asyncio.CancelledError:
            if prepare_attempted:
                self._schedule_cleanup(call_id, caller_id)
            raise
        except BaseException as exc:
            if prepare_attempted or prepared:
                self._schedule_cleanup(call_id, caller_id)
            if self._is_current(call_id):
                failure_type = getattr(self.readiness, "error_type", None) or type(exc).__name__
                self.sip_media.reject(self.failure_status_code, f"ai_readiness_failed:{failure_type}")
        finally:
            if self._pending_call_id == call_id:
                self._pending_call_id = None
                self._pending_caller_id = None
            if self._task is asyncio.current_task():
                self._task = None

    async def _run_hook(
        self,
        hook: Callable[[str, str], object],
        call_id: str,
        caller_id: str,
        timeout_s: float,
    ) -> object:
        worker = asyncio.create_task(asyncio.to_thread(hook, call_id, caller_id))
        self._preparation_tasks[call_id] = worker
        done, _ = await asyncio.wait({worker}, timeout=timeout_s)
        if not done:
            # Do not cancel the thread-backed work.  A late index publication
            # must be followed by cleanup before another call can use it.
            raise TimeoutError(f"call preparation exceeded {timeout_s:.1f}s")
        try:
            result = await worker
            if inspect.isawaitable(result):
                return await asyncio.wait_for(result, timeout=timeout_s)
            return result
        finally:
            self._preparation_tasks.pop(call_id, None)

    def _schedule_cleanup(self, call_id: str, caller_id: str | None) -> None:
        if self.call_cleanup is None or caller_id is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(
            self._run_cleanup_after_preparation(call_id, caller_id),
            name=f"sip-bot-rag-cleanup-{call_id}",
        )
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)

    async def _run_cleanup(self, call_id: str, caller_id: str) -> None:
        try:
            result = await asyncio.to_thread(self.call_cleanup, call_id, caller_id)
            if inspect.isawaitable(result):
                await result
        except BaseException:
            # Cleanup is best-effort at the protocol edge; the web session
            # endpoint remains an idempotent secondary cleanup path.
            return

    async def _run_cleanup_after_preparation(self, call_id: str, caller_id: str) -> None:
        worker = self._preparation_tasks.get(call_id)
        if worker is not None:
            try:
                await asyncio.shield(worker)
            except BaseException:
                pass
            finally:
                self._preparation_tasks.pop(call_id, None)
        await self._run_cleanup(call_id, caller_id)

    def _is_current(self, call_id: str) -> bool:
        if self._closed or self._pending_call_id != call_id:
            return False
        if hasattr(self.sip_media, "active_call_id"):
            return getattr(self.sip_media, "active_call_id") == call_id
        return True

    def _cancel_pending(self) -> None:
        task = self._task
        self._task = None
        self._pending_call_id = None
        self._pending_caller_id = None
        if task is not None and not task.done():
            task.cancel()


def _caller_id_from_details(details: dict[str, object]) -> str | None:
    value = details.get("caller_id")
    return value if isinstance(value, str) and value else None


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
        incoming_admission: IncomingCallReadinessGate | None = None,
        semantic_parser: SemanticTurnParser | None = None,
        clock_ns: Callable[[], int] = monotonic_ns,
        latency_sink: TtsLatencySink | None = None,
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
        for name in ("submit_semantic_turn", "drain_control"):
            if not callable(getattr(pipeline, name, None)):
                raise TypeError(f"pipeline must provide {name}()")
        self.composition = composition
        self.sip_media = sip_media
        self.speech = speech
        self.asr = asr
        self.pipeline = pipeline
        self.semantic_parser = semantic_parser or SemanticTurnParser()
        self.config = config or RuntimeConfig.from_constants()
        if incoming_admission is not None and incoming_admission.sip_media is not sip_media:
            raise ValueError("incoming_admission must own the supplied sip_media instance")
        self.incoming_admission = incoming_admission
        self.clock_ns = clock_ns
        self.latency_sink = latency_sink
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
        self._speech_frame_turns: dict[int, str] = {}
        self._candidate_speech_sequences: list[int] = []
        self._candidate_asr_frames: list[PcmFrame] = []
        self._playback_lock = Lock()
        self._outputs: dict[tuple[str, int], TtsOutputBuffer] = {}
        self._playback: dict[tuple[str, int], PlaybackChannel] = {}
        self._pending_physical_close: set[tuple[str, int]] = set()
        self._speech_event_sequence = 0
        self._previous_audio_sink = getattr(pipeline, "audio_sink", None)
        self._sip_event_sink = _WiringSipEventSink(self)
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
            self.sip_media.event_sink = self._sip_event_sink
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
        if self.incoming_admission is not None:
            self.incoming_admission.close()
        if self._chunker is not None:
            self._chunker.cancel()
        self.asr.close()
        self.speech.close()
        self.pipeline.close(reason) if callable(getattr(self.pipeline, "close", None)) else None
        worker = self._asr_thread
        if worker is not None:
            worker.join(timeout=1.0)
        self._asr_thread = None
        self._speech_frame_turns.clear()
        self._candidate_speech_sequences.clear()
        self._candidate_asr_frames.clear()
        self._started = False

    def _drain_media_ingress(self) -> None:
        # An incoming INVITE is first observed as a control event.  Until the
        # adapter has materialized its call context there is no media source
        # to poll; asking the native adapter for a frame at that point would
        # raise ``no active call`` and abort the main loop.
        if hasattr(self.sip_media, "active_call_id") and getattr(self.sip_media, "active_call_id") is None:
            return
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
                self._candidate_speech_sequences.append(frame.sequence)
                turn_id = self.speech.turn_detector.active_turn_id
                if turn_id is not None:
                    assert self._chunker is not None
                    if self._chunker.active_turn_id is None:
                        self._chunker.begin_turn(turn_id)
                    elif self._chunker.active_turn_id != turn_id:
                        raise RuntimeWiringError(
                            "TurnDetector changed turn before the ASR accumulator received its hard endpoint"
                        )
                    for sequence in self._candidate_speech_sequences:
                        self._speech_frame_turns[sequence] = turn_id
                    self._candidate_speech_sequences.clear()
                    self._flush_qualified_candidate_frames(turn_id)
            elif self.speech.turn_detector.active_turn_id is None:
                # WebRTC/energy-positive bursts shorter than min_speech_ms are
                # not user turns and must not contaminate the next ASR prefix.
                self._candidate_speech_sequences.clear()
                self._candidate_asr_frames.clear()
            self._publish_speech_events(result.endpoint_events, result.vad_decision)
            if self.speech.defer_endpoint_finalization and self._chunker is not None:
                for event in result.endpoint_events:
                    if event.kind is EndpointEventKind.HARD_ENDPOINT:
                        # The hard-endpoint chunk is the ASR-side commit marker.
                        # It retains the authoritative TurnDetector turn_id so
                        # delayed worker results cannot finalize another turn.
                        self._queue_ready_chunks(self._chunker.hard_endpoint(event.turn_id))
            if result.final_turn is not None:
                self._deliver_final_turn(result.final_turn)

    def _publish_speech_events(
        self,
        events: tuple[EndpointEvent, ...],
        decision: Any | None = None,
    ) -> None:
        """Materialize speech lifecycle outputs on the existing control edge.

        ``SpeechIngress`` owns VAD/endpointing and returns typed endpoint data;
        the runtime only adapts that output to the already accepted compact
        FSM control event.  A speech start/resume while playback is active is
        explicitly classified as ``barge_in`` so the FSM closes playback
        before the next authoritative turn is accepted.
        """

        barge_in_submitted = False
        for event in events:
            self._speech_event_sequence += 1
            kind = _speech_event_kind(event.kind)
            playback_active = self.composition.fsm.state.value in {"playing", "offering_transfer"}
            if (
                event.kind in {EndpointEventKind.SPEECH_STARTED, EndpointEventKind.SPEECH_RESUMED}
                and playback_active
            ):
                if decision is not None and decision.barge_in_qualified is False:
                    # Keep endpointing/ASR state local, but do not let weak
                    # acoustic return mutate the playback control state.
                    continue
                kind = SpeechEventKind.BARGE_IN
                barge_in_submitted = True
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

        # A weak acoustic-return frame can be the frame on which TurnDetector
        # emits SPEECH_STARTED.  If near-end speech then becomes strong enough
        # during the same active turn, no second start event is emitted.  The
        # frame-level typed decision therefore completes the existing control
        # edge once the already-open turn is positively qualified.
        playback_active = self.composition.fsm.state.value in {"playing", "offering_transfer"}
        if (
            not barge_in_submitted
            and playback_active
            and decision is not None
            and decision.is_speech
            and decision.barge_in_qualified is True
            and self.speech.turn_detector.active_turn_id is not None
        ):
            self._speech_event_sequence += 1
            accepted = self.composition.submit_control(
                SpeechEvent(
                    decision.call_id,
                    SpeechEventKind.BARGE_IN,
                    sequence=self._speech_event_sequence,
                    channel_id=decision.channel_id,
                    channel_generation=decision.generation,
                    reason="near_end_speech_qualified_during_active_turn",
                )
            )
            if not accepted:
                self._record_error(RuntimeWiringError("Dispatcher rejected SpeechEvent"))

    def _drain_asr_audio(self) -> None:
        if self._asr_input_subscription is None or self._chunker is None:
            return
        for frame in self._drain_subscription(self._asr_input_subscription):
            turn_id = self._speech_frame_turns.pop(frame.sequence, None)
            if turn_id is None:
                if frame.sequence in self._candidate_speech_sequences:
                    self._candidate_asr_frames.append(frame)
                continue
            if self._chunker.active_turn_id != turn_id:
                raise RuntimeWiringError("ASR frame turn_id does not match the active accumulator turn")
            self._queue_ready_chunks(self._chunker.push(frame))

    def _flush_qualified_candidate_frames(self, turn_id: str) -> None:
        if self._chunker is None or not self._candidate_asr_frames:
            return
        pending = tuple(self._candidate_asr_frames)
        self._candidate_asr_frames.clear()
        for frame in pending:
            mapped_turn_id = self._speech_frame_turns.pop(frame.sequence, None)
            if mapped_turn_id != turn_id:
                raise RuntimeWiringError("qualified ASR pre-roll lost its TurnDetector turn_id")
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
            update = self.speech.accept_hypothesis(hypothesis)
            if not hypothesis.speech_supported:
                self.stats.asr_rejected_hypotheses += 1
            elif update is None:
                self.stats.stale_hypotheses += 1
                continue
            final_turn = self.speech.take_final_turn()
            if final_turn is not None:
                self._deliver_final_turn(final_turn)

    def _deliver_final_turn(self, final_turn: Any) -> None:
        """Deliver only a current-generation final turn to the pipeline.

        ASR can finish a queued chunk after a protocol terminal event or a
        completed transfer has already closed the call session.  Such a value
        is stale by the existing lifecycle contract and must be discarded,
        not reported as a pipeline error.
        """

        lease = SessionLease(final_turn.call_id, final_turn.generation)
        if self.composition.fsm.is_terminal or not self.composition.session.accepts(lease):
            return
        self.stats.final_turns += 1
        semantic_turn = self.semantic_parser.parse(
            final_turn,
            self.composition.fsm.current_expectation(),
        )
        if not self.pipeline.submit_semantic_turn(semantic_turn):
            self._record_error(RuntimeWiringError("ConversationPipeline rejected current SemanticTurn"))

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

    def _on_sip_event(self, event: NormalizedSipEvent) -> None:
        """Publish SIP control, then schedule readiness outside callbacks."""

        # Registration lifecycle events use the adapter's reserved control
        # identity and do not belong to the active call Dispatcher/FSM.  They
        # must remain available to the runtime/registration owner, but
        # feeding them into a call-scoped Dispatcher violates its session
        # contract before the first CALL_STARTED event.
        if event.call_id == self.composition.session.call_id:
            if hasattr(self.composition.dispatcher, "publish"):
                self.composition.dispatcher.publish(event)
            else:
                self.composition.submit_control(event)
        if self.incoming_admission is not None:
            try:
                self.incoming_admission.observe(event)
            except BaseException as exc:
                self._record_error(exc)

    def _on_control_submitted(self, event: object, accepted: bool) -> None:
        if not accepted or not isinstance(event, DialoguePlaybackEvent):
            return
        if event.status in {PlaybackStatus.PRODUCER_COMPLETED, PlaybackStatus.COMPLETED}:
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
            if self.latency_sink is not None:
                try:
                    self.latency_sink(
                        TtsLatencyEvent(
                            operation_id=f"playback-{event.channel_id}-{event.generation}",
                            call_id=event.call_id,
                            turn_id="",
                            channel_id=event.channel_id,
                            generation=event.generation,
                            stage=TtsLatencyStage.PLAYBACK_FIRST_FRAME,
                            timestamp_ns=event.timestamp_ns,
                        )
                    )
                except Exception:
                    pass
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
                producer_complete = key in self._pending_physical_close
                output_drained = output is not None and output.pending_frames == 0
            if producer_complete and output_drained:
                # The application output buffer has been handed to the SIP
                # bridge. Keep the FSM in PLAYING until PJMEDIA has consumed
                # the bridge's own egress buffer as well.
                self._set_egress_source_mode(EgressSourceMode.DRAINING)
                if self._egress_pending_frames() > 0:
                    continue
            else:
                continue
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

    def _egress_pending_frames(self) -> int:
        getter = getattr(self.sip_media, "egress_pending_frames", None)
        if not callable(getter):
            # Test doubles and non-PJMEDIA adapters without a physical queue
            # are treated as already drained.
            return 0
        try:
            return max(0, int(getter()))
        except RuntimeError:
            if getattr(self.sip_media, "active_call_id", None) is None:
                return 0
            raise

    def _record_error(self, error: BaseException) -> None:
        self.stats.errors += 1
        self.errors.append(f"{type(error).__name__}: {error}")


def _speech_event_kind(kind: EndpointEventKind) -> SpeechEventKind:
    """Map the speech owner's lifecycle enum to the FSM control enum."""

    return SpeechEventKind(kind.value)


__all__ = ["CallRuntimeWiring", "IncomingCallReadinessGate", "RuntimeWiringError", "RuntimeWiringStats"]
