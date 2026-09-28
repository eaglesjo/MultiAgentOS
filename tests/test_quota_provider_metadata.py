from runtime.model.native import _openai_rate_limits, _usage_dict


def test_openai_rate_limit_headers_are_normalized():
    result = _openai_rate_limits(
        {
            "x-ratelimit-limit-requests": "100",
            "x-ratelimit-remaining-requests": "73",
            "x-ratelimit-reset-requests": "1.5s",
            "x-ratelimit-limit-tokens": "50000",
            "x-ratelimit-remaining-tokens": "49000",
            "x-ratelimit-reset-tokens": "2s",
        }
    )
    assert result["requests"]["limit"] == 100
    assert result["requests"]["remaining"] == 73
    assert result["requests"]["reset_seconds"] == 1.5
    assert result["tokens"]["remaining"] == 49000


def test_provider_usage_metadata_is_normalized():
    usage = _usage_dict(
        {
            "promptTokenCount": 120,
            "candidatesTokenCount": 30,
            "totalTokenCount": 150,
        }
    )
    assert usage == {
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
    }
