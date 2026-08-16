from app.services.runs import RunService


def test_capabilities_include_all_modes_and_tools(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert {mode["id"] for mode in body["execution_modes"]} == {
        "single",
        "judge",
        "jury",
        "debate",
        "debate_judge",
        "debate_jury",
    }
    assert {tool["id"] for tool in body["tools"]} == {"current_time", "calculator"}


def test_conversation_crud(client) -> None:  # type: ignore[no-untyped-def]
    created = client.post("/api/v1/conversations", json={"title": "Home tasks"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    assert client.get("/api/v1/conversations").json()[0]["title"] == "Home tasks"
    updated = client.patch(f"/api/v1/conversations/{conversation_id}", json={"title": "Updated"})
    assert updated.json()["title"] == "Updated"
    assert client.delete(f"/api/v1/conversations/{conversation_id}").status_code == 204


def test_run_validates_participant_layout(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/runs",
        json={
            "prompt": "hello",
            "execution_mode": "judge",
            "model_id": "test-model-a",
            "participants": [
                {
                    "id": "primary",
                    "role": "primary",
                    "model_id": "test-model-a",
                    "reasoning_effort": "medium",
                }
            ],
        },
    )
    assert response.status_code == 422
    assert "Participants must exactly match" in response.json()["detail"]


def test_conversation_run_is_scheduled_on_app_event_loop(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def execute_without_provider_call(_service: RunService, _run_id: str) -> None:
        return None

    monkeypatch.setattr(RunService, "_execute", execute_without_provider_call)
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Run scheduling"}
    ).json()

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/runs",
        json={
            "prompt": "hello",
            "execution_mode": "single",
            "model_id": "test-model-a",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_first_prompt_titles_default_conversation(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def execute_without_provider_call(_service: RunService, _run_id: str) -> None:
        return None

    monkeypatch.setattr(RunService, "_execute", execute_without_provider_call)
    conversation = client.post("/api/v1/conversations", json={}).json()

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/runs",
        json={
            "prompt": "  Help me   plan a vegetable garden for the spring  ",
            "execution_mode": "single",
            "model_id": "test-model-a",
        },
    )

    assert response.status_code == 202
    conversations = client.get("/api/v1/conversations").json()
    assert conversations[0]["title"] == "Help me plan a vegetable garden for the spring"

    second_response = client.post(
        f"/api/v1/conversations/{conversation['id']}/runs",
        json={
            "prompt": "This later prompt must not replace the title",
            "execution_mode": "single",
            "model_id": "test-model-a",
        },
    )

    assert second_response.status_code == 202
    conversations = client.get("/api/v1/conversations").json()
    assert conversations[0]["title"] == "Help me plan a vegetable garden for the spring"
