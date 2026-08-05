from types import SimpleNamespace

from core.manager import Manager


def test_manager_replaces_timed_out_conversation_before_next_message(monkeypatch):
    manager = Manager.__new__(Manager)
    manager.conversation = SimpleNamespace(name="old")
    manager.conversation_needs_reset = True
    manager.conversation_mode = "multi_agent"
    manager.retired_conversations = []
    manager.log = lambda _message: None
    setup_modes = []

    def setup(mode):
        setup_modes.append(mode)
        manager.conversation = SimpleNamespace(name="new")
        manager.conversation_needs_reset = False

    monkeypatch.setattr(manager, "setup", setup)

    manager.ensure_usable_conversation()

    assert setup_modes == ["multi_agent"]
    assert manager.conversation.name == "new"
    assert [conversation.name for conversation in manager.retired_conversations] == [
        "old"
    ]
