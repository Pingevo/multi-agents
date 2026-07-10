"""Chainlit action callbacks: plan accept/reject, agent CRUD, task assignment."""

import json
import traceback

import chainlit as cl
from backend.globals import *
from backend.utils import _sanitize_error, _debug
from backend.llm.manager import LLMManager
from backend.agents.registry import AgentRegistry
from backend.agents.tool_registry import ToolRegistry
from backend.core.orchestrator import ExecutionOrchestrator
from backend.core.messenger import StateMessenger
from schemas import chat_reply


def get_messenger() -> StateMessenger:
    """Get the StateMessenger from Chainlit user session."""
    import chainlit as cl
    return cl.user_session.get("messenger")


# ============================================================
# Action Handlers
# ============================================================
@cl.action_callback("confirm_create_agent")
async def on_action_create_agent(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state != STATE_CREATING_AGENT:
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    agent_specs = cl.user_session.get("current_agent_specs")
    user_input = cl.user_session.get("current_input")
    registry = cl.user_session.get("registry") or AgentRegistry()

    primary_spec = agent_specs[0] if agent_specs else None
    if not primary_spec:
        if messenger:
            await messenger.notify("❌ ไม่พบข้อมูล Agent ที่ต้องสร้าง")
        cl.user_session.set("state", STATE_IDLE)
        return

    new_agent = registry.add_agent(primary_spec)
    merged_spec = registry.to_spec(new_agent)
    merged_spec["task_description"] = primary_spec.get("task_description", user_input)
    merged_spec["registry_id"] = new_agent.get("id")

    cl.user_session.set("current_agent_specs", [merged_spec])
    cl.user_session.set("current_registry_id", new_agent.get("id"))
    cl.user_session.set("state", STATE_AWAITING_APPROVAL)

    if messenger:
        await messenger.update_agents(registry)
        await messenger.set_plan(
            messenger._agents_for_ui([new_agent])[0],
            merged_spec.get("task_description", user_input),
            plan_type="new",
        )
        await messenger.notify(f"✅ สร้าง Agent {new_agent['name']} และบันทึกลงทะเบียนแล้ว")


@cl.action_callback("accept_plan")
async def on_action_accept(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state not in (STATE_AWAITING_APPROVAL, STATE_CREATING_AGENT):
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    user_input = cl.user_session.get("current_input")
    agent_specs = cl.user_session.get("current_agent_specs")
    registry = cl.user_session.get("registry") or AgentRegistry()

    if not agent_specs:
        if messenger:
            await messenger.notify("❌ ไม่พบข้อมูล Agent สำหรับประมวลผล")
        cl.user_session.set("state", STATE_IDLE)
        return

    # Resolve models from pre_assigned_models into specs for validation
    pre_assigned = cl.user_session.get("pre_assigned_models")
    for spec in agent_specs:
        name = spec.get("name", "")
        if pre_assigned and name and pre_assigned.get("workers", {}).get(name):
            spec["model"] = pre_assigned["workers"][name]

    # Register all new agents in the plan
    registered_specs = []
    for spec in agent_specs:
        if spec.get("registry_id"):
            # Already registered
            registered_specs.append(spec)
        else:
            new_agent = registry.add_agent(spec)
            merged = registry.to_spec(new_agent)
            merged["task_description"] = spec.get("task_description", user_input)
            merged["depends_on"] = spec.get("depends_on", [])
            merged["registry_id"] = new_agent.get("id")
            registered_specs.append(merged)

    cl.user_session.set("current_agent_specs", registered_specs)
    if messenger:
        messenger.update_plan_status("approved")
        await messenger.update_agents(registry)
        await messenger.clear_plan()
        await messenger.notify("🚀 กำลังเตรียม agents และเริ่มประมวลผล...")

    from backend.handlers.chat import execute_multi_agent_task
    await execute_multi_agent_task(user_input, registered_specs, registry)

    cl.user_session.set("attachment_context", None)
    cl.user_session.set("attachment_crewai_files", None)
    cl.user_session.set("last_attachment_url", None)
    cl.user_session.set("last_attachment_name", None)
    cl.user_session.set("last_attachment_mime", None)


@cl.action_callback("reject_plan")
async def on_action_reject(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state not in (STATE_AWAITING_APPROVAL, STATE_CREATING_AGENT):
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)
    cl.user_session.set("current_registry_id", None)
    if messenger:
        messenger.update_plan_status("rejected")
        await messenger.clear_plan()
        await messenger.reply("🔄 แผนงานถูกปฏิเสธ กรุณาพิมพ์คำสั่งใหม่หรืออธิบายเพิ่มเติม")


@cl.action_callback("cancel_plan")
async def on_action_cancel(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state not in (STATE_AWAITING_APPROVAL, STATE_CREATING_AGENT):
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)
    cl.user_session.set("current_registry_id", None)
    if messenger:
        await messenger.clear_plan()
        await messenger.notify("❌ แผนงานถูกยกเลิกแล้ว")


@cl.action_callback("add_agent_form")
async def on_action_add_agent_form(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    payload = action.payload or {}

    spec = {
        "name": payload.get("name", "Unnamed"),
        "role": payload.get("role", ""),
        "goal": payload.get("goal", ""),
        "backstory": payload.get("persona", ""),
        "persona": payload.get("persona", ""),
        "tools": [t.strip() for t in payload.get("tools", "").split(",") if t.strip()],
        "model": payload.get("model", ""),
    }

    try:
        new_agent = registry.add_agent(spec)
        if messenger:
            await messenger.update_agents(registry)
            await messenger.notify(f"✅ สร้าง Agent {new_agent['name']} สำเร็จ")
    except Exception as e:
        if messenger:
            await messenger.notify(f"❌ สร้าง Agent ไม่สำเร็จ: {str(e)}")


@cl.action_callback("edit_agent_form")
async def on_action_edit_agent_form(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    payload = action.payload or {}
    agent_id = payload.get("agent_id")

    if not agent_id:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ID")
        return

    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ที่ต้องการแก้ไข")
        return

    spec = {
        "name": payload.get("name", agent.get("name")),
        "role": payload.get("role", agent.get("role")),
        "goal": payload.get("goal", agent.get("goal")),
        "persona": payload.get("persona", agent.get("persona")),
        "tools": [t.strip() for t in payload.get("tools", "").split(",") if t.strip()],
        "model": payload.get("model", agent.get("model", "")),
    }

    try:
        registry.update_agent(agent_id, spec)
        if messenger:
            await messenger.update_agents(registry)
            await messenger.notify(f"✅ แก้ไข Agent {agent_id} สำเร็จ")
    except Exception as e:
        if messenger:
            await messenger.notify(f"❌ แก้ไข Agent ไม่สำเร็จ: {str(e)}")


@cl.action_callback("delete_agent")
async def on_action_delete_agent(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    agent_id = action.payload.get("agent_id")
    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ที่ต้องการลบ")
        return

    registry.delete_agent(agent_id)
    if messenger:
        await messenger.update_agents(registry)


@cl.action_callback("assign_task_form")
async def on_action_assign_task_form(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    payload = action.payload or {}
    agent_id = payload.get("agent_id")
    task_description = payload.get("task", "").strip()

    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ที่ต้องการมอบหมายงาน")
        return

    if agent.get("status") != "Idle":
        if messenger:
            await messenger.notify(f"⚠️ Agent {agent.get('name')} กำลัง Busy")
        return

    if not task_description:
        if messenger:
            await messenger.notify("❌ กรุณาระบุรายละเอียดงาน")
        return

    agent_spec = registry.to_spec(agent)
    agent_spec["task_description"] = task_description
    agent_spec["registry_id"] = agent_id

    if messenger:
        await messenger.notify(f"🚀 มอบหมายงานให้ {agent.get('name')}")

    from backend.handlers.chat import execute_task_with_agent
    await execute_task_with_agent(task_description, agent_spec, agent_id, registry)



