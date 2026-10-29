from unittest.mock import Mock

import pytest

from bruhanimate import (
    ActionQueue,
    Animation,
    AnimationControl,
    Buffer,
    KeyBinding,
    KeyBindings,
    Layer,
    Scene,
    SnowEffect,
    SnowSettings,
    Sprite,
    SpriteAsset,
)


def child():
    return Mock(spec=Animation)


@pytest.mark.parametrize("mode", ["fixed", "continuous"])
def test_pause_zero_scale_and_zero_dt_never_forward_update(mode):
    animation = child()
    control = AnimationControl(animation, mode=mode)
    control.start()
    control.update(0)
    control.time_scale = 0
    control.update(10)
    control.time_scale = 1
    control.pause()
    control.update(100)
    control.draw(Buffer(1, 1))
    animation.update.assert_not_called()
    animation.draw.assert_called_once()
    control.resume()
    control.update(1 / 30)
    animation.update.assert_called_once_with(1 / 30)
    control.close()


@pytest.mark.parametrize("fps", [20, 30, 60, 120])
def test_half_speed_seeded_builtin_matches_half_number_of_ticks(fps):
    expected = SnowEffect(Buffer(8, 18), " ", SnowSettings(seed=19, intensity=0.1))
    actual = SnowEffect(Buffer(8, 18), " ", SnowSettings(seed=19, intensity=0.1))
    control = AnimationControl(actual, mode="fixed", time_scale=0.5)
    expected.start()
    control.start()
    try:
        for _ in range(30):
            expected.update(1 / 30)
        for _ in range(fps * 2):
            control.update(1 / fps)
        first, second = Buffer(8, 18), Buffer(8, 18)
        expected.draw(first)
        control.draw(second)
        assert first.buffer == second.buffer
        # Continue both: compare RNG/simulation state, not just an accidentally equal frame.
        expected.update(1 / 30)
        control.update(2 / 30)
        expected.draw(first)
        control.draw(second)
        assert first.buffer == second.buffer
    finally:
        control.close()
        expected.close()


@pytest.mark.parametrize("mode", ["fixed", "continuous"])
@pytest.mark.parametrize("fps", [20, 60])
def test_continuous_sprite_travels_half_distance(mode, fps):
    sprite = Sprite(SpriteAsset.from_text("x"), velocity=(6, 0))
    control = AnimationControl(sprite, mode=mode, time_scale=0.5)
    control.start()
    for _ in range(fps * 2):
        control.update(1 / fps)
    assert sprite.position[0] == pytest.approx(6)
    control.close()


def test_fractional_time_survives_pause_scale_resize_and_manual_step():
    animation = child()
    control = AnimationControl(animation, mode="fixed", step_seconds=1)
    control.start()
    control.update(0.4)
    control.pause()
    control.step()
    control.step()
    control.time_scale = 0
    control.update(100)
    animation.update.assert_called_once_with(1)
    control.update(100)
    assert animation.update.call_count == 1
    control.resize((2, 3))
    control.resume()
    control.time_scale = 0.5
    control.update(1.2)
    assert animation.update.call_count == 2
    control.close()


@pytest.mark.parametrize("mode", ["fixed", "continuous"])
def test_steps_are_queued_resume_cancels_and_finished_child_stops(mode):
    animation = child()
    animation.finished = False
    control = AnimationControl(animation, mode=mode, paused=True, step_seconds=0.2)
    control.step()
    control.start()
    control.draw(Buffer(1, 1))
    animation.update.assert_not_called()
    control.resume()
    control.pause()
    control.update(0)
    animation.update.assert_not_called()
    control.step()
    control.update(0)
    animation.update.assert_called_once_with(0.2)
    animation.finished = True
    control.step()
    control.update(10)
    assert control.finished is True and animation.update.call_count == 1
    control.close()


def test_fixed_clock_matches_scene_catchup_and_discards_remainder_at_cap():
    a, b = child(), child()
    control = AnimationControl(a, mode="fixed", step_seconds=0.1, max_catch_up=3)
    scene = Scene(Layer(b, updates_per_second=10, max_catch_up=3))
    control.start()
    scene.start()
    for dt in (0.04, 0.07, 0.32, 0.05, 0.06, 1e300):
        control.update(dt)
        scene.update(dt)
        assert a.update.call_args_list == b.update.call_args_list
    before = a.update.call_count
    control.update(0.05)
    assert a.update.call_count == before
    control.close()
    scene.close()


def test_completion_and_pause_during_catchup_stop_further_ticks():
    animation = child()
    animation.finished = False
    control = AnimationControl(animation, mode="fixed")
    animation.update.side_effect = lambda dt: control.pause()
    control.start()
    control.update(1)
    assert animation.update.call_count == 1
    control.resume()
    animation.update.side_effect = lambda dt: setattr(animation, "finished", True)
    control.update(1)
    assert animation.update.call_count == 2
    control.close()


@pytest.mark.parametrize(
    "options",
    [
        {"mode": "bad"},
        {"step_seconds": 0},
        {"step_seconds": float("nan")},
        {"time_scale": -1},
        {"paused": 1},
        {"max_catch_up": True},
        {"max_catch_up": 0},
    ],
)
def test_invalid_controls_do_not_acquire_child(options):
    animation = child()
    with pytest.raises((TypeError, ValueError)):
        AnimationControl(animation, **{"mode": "fixed", **options})
    animation.start.assert_not_called()
    animation.close.assert_not_called()


def test_overflow_invalid_dt_and_scale_leave_state_unchanged():
    animation = child()
    control = AnimationControl(animation, mode="fixed", time_scale=2)
    control.start()
    for dt in (float("nan"), -1, True, 1e308):
        with pytest.raises((TypeError, ValueError)):
            control.update(dt)
    with pytest.raises(ValueError):
        control.time_scale = -1
    assert control.time_scale == 2
    animation.update.assert_not_called()
    control.update(1 / 60)
    animation.update.assert_called_once()
    control.close()


@pytest.mark.parametrize("started,fail", [(False, False), (True, False), (True, True)])
def test_owned_cleanup_startup_failure_and_single_use(started, fail):
    animation = child()
    control = AnimationControl(animation, mode="fixed")
    if fail:
        animation.start.side_effect = RuntimeError("start failed")
        with pytest.raises(RuntimeError):
            control.start()
    elif started:
        control.start()
        control.start()
        animation.start.assert_called_once()
    control.close()
    control.close()
    animation.close.assert_called_once()
    with pytest.raises(RuntimeError):
        control.start()
    with pytest.raises(RuntimeError):
        control.update(0)
    with pytest.raises(RuntimeError):
        control.step()


def test_visibility_resize_forward_without_updating_and_close_failure_is_idempotent():
    animation = child()
    animation.resize = Mock()
    animation.set_visible = Mock()
    control = AnimationControl(animation, mode="continuous", paused=True)
    control.resize((5, 2))
    control.set_visible(False)
    animation.resize.assert_called_once_with((5, 2))
    animation.set_visible.assert_called_once_with(False)
    animation.update.assert_not_called()
    animation.close.side_effect = RuntimeError("close failed")
    with pytest.raises(RuntimeError):
        control.close()
    control.close()
    animation.close.assert_called_once()


def test_queue_overflow_order_snapshots_and_keybinding_adapter():
    queue = ActionQueue[str](capacity=2)
    binding = KeyBindings(KeyBinding("space", queue.bind("jump")))
    assert len(queue) == 0
    assert not binding.handle_event(32)
    assert queue.push("move")
    assert not queue.push("discarded")
    batch = queue.drain(limit=100)
    assert batch == ("jump", "move")
    for action in batch:
        queue.push(action + "-next")
    assert batch == ("jump", "move")
    assert queue.drain(limit=0) == () and len(queue) == 2
    assert queue.drain() == ("jump-next",)
    queue.clear()
    assert queue.drain() == ()


@pytest.mark.parametrize("bad", [True, -1, 1.5, "2"])
def test_queue_limits_are_validated_atomically(bad):
    with pytest.raises(ValueError):
        ActionQueue(capacity=bad)
    queue = ActionQueue[int]()
    queue.push(1)
    with pytest.raises(ValueError):
        queue.drain(limit=bad)
    assert len(queue) == 1


def test_control_demo_routes_queued_pause_step_speed_and_retains_state_on_resize():
    from bruhanimate.demos.controls_demo import build

    demo = build(Buffer(8, 40))
    demo.start()
    try:
        demo.handle_event(32)
        assert not demo.motion.paused
        demo.update(1 / 30)
        assert demo.motion.paused and demo.marker.position[0] == 0
        demo.handle_event(ord("n"))
        demo.update(100)
        assert demo.marker.position[0] == pytest.approx(0.2)
        demo.handle_event(ord("1"))
        demo.handle_event(32)
        demo.update(1)
        assert demo.marker.position[0] == pytest.approx(3.2)
        demo.resize((20, 5))
        assert demo.marker.position[0] == pytest.approx(3.2)
        assert demo.motion.time_scale == demo.snow.time_scale == 0.5
        assert demo.handle_event(ord("q"))
    finally:
        demo.close()
