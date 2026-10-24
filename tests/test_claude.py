from unittest.mock import Mock
import pytest
from agent import llm


def test_claude_messages_separates_system_and_bounds_output(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Mock(is_success=True, json=lambda: {'stop_reason':'end_turn', 'content':[{'type':'text','text':'{"verdict":"match"}'}]})
    monkeypatch.setattr('httpx.post', post)
    result = llm.ClaudeMessages('fake-secret').complete([
        {'role':'system','content':'Verify payment'}, {'role':'user','content':'Request'}],
        model='claude-haiku-4-5-20251001', temperature=0, json_mode=True)
    url, kw = calls[0]
    assert url == 'https://api.anthropic.com/v1/messages'
    assert kw['headers']['x-api-key'] == 'fake-secret'
    assert kw['json']['max_tokens'] == 1200
    assert kw['json']['messages'] == [{'role':'user','content':'Request'}]
    assert 'valid JSON' in kw['json']['system']
    assert llm.extract_json(result)['verdict'] == 'match'


@pytest.mark.parametrize('code', [401, 429, 500])
def test_claude_errors_do_not_expose_response_body(monkeypatch, code):
    monkeypatch.setattr('httpx.post', lambda *a, **kw: Mock(is_success=False, status_code=code, text='secret'))
    with pytest.raises(llm.ModelAPIError) as caught:
        llm.ClaudeMessages('fake-secret').complete([], model='haiku', temperature=0, json_mode=False)
    assert caught.value.status_code == code
    assert 'secret' not in str(caught.value)


def test_truncated_json_is_not_used(monkeypatch):
    monkeypatch.setattr('httpx.post', lambda *a, **kw: Mock(is_success=True,
        json=lambda: {'stop_reason':'max_tokens','content':[{'type':'text','text':'{'}]}))
    with pytest.raises(RuntimeError, match='budget'):
        llm.ClaudeMessages('fake').complete([], model='haiku', temperature=0, json_mode=True)


def test_claude_selected_over_old_grok_key(monkeypatch):
    monkeypatch.setattr(llm, 'dotenv_values', lambda _: {'CLAUDE_API_KEY':'fake-claude', 'X_API_KEY':'old-key'})
    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    assert llm.configuration() == ('anthropic','fake-claude','claude-haiku-4-5-20251001')
