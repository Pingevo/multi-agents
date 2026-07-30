"""Chainlit action callbacks: plan accept/reject, agent CRUD, task assignment."""

import json
import traceback
from datetime import datetime

import chainlit as cl
from backend.globals import *
from backend.utils import _sanitize_error, _debug
from backend.llm.manager import LLMManager
from backend.agents.registry import AgentRegistry
from backend.agents.tool_registry import ToolRegistry
from backend.agents.team_registry import TeamRegistry
from backend.agents.chat_store import ChatStore
from backend.agents.task_store import TaskStore
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
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)

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
        _tid = cl.user_session.get("current_team_id")
        await messenger.update_agents(registry, team_id=_tid)
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
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)

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
    current_team_id = cl.user_session.get("current_team_id")
    team_registry = cl.user_session.get("team_registry") or TeamRegistry()
    registered_specs = []
    print(f"[DEBUG-ACCEPT] Registering {len(agent_specs)} specs, plan_type={cl.user_session.get('current_plan_type')}, team_id={current_team_id}", flush=True)
    for spec in agent_specs:
        if spec.get("registry_id"):
            # Already registered
            print(f"[DEBUG-ACCEPT] Agent '{spec.get('name')}' already registered (id={spec.get('registry_id')})", flush=True)
            registered_specs.append(spec)
        else:
            if current_team_id:
                spec["team_id"] = current_team_id
            new_agent = registry.add_agent(spec)
            print(f"[DEBUG-ACCEPT] Registered agent: {new_agent.get('name')} (id={new_agent.get('id')})", flush=True)
            merged = registry.to_spec(new_agent)
            merged["task_description"] = spec.get("task_description", user_input)
            merged["depends_on"] = spec.get("depends_on", [])
            merged["registry_id"] = new_agent.get("id")
            if current_team_id:
                team_registry.add_agent(current_team_id, new_agent.get("id"))
            registered_specs.append(merged)
    cl.user_session.set("team_registry", team_registry)

    cl.user_session.set("current_agent_specs", registered_specs)

    # Auto-apply: if Manager adjusted goal/persona/tools of existing agents, persist immediately
    for spec in registered_specs:
        reg_id = spec.get("registry_id", "")
        if not reg_id:
            continue
        agent_in_registry = None
        for a in registry.list_agents():
            if a.get("id") == reg_id:
                agent_in_registry = a
                break
        if not agent_in_registry:
            continue
        update_fields = {}
        if agent_in_registry.get("goal", "") != spec.get("goal", ""):
            update_fields["goal"] = spec.get("goal", "")
        if agent_in_registry.get("persona", "") != spec.get("persona", spec.get("backstory", "")):
            update_fields["persona"] = spec.get("persona", spec.get("backstory", ""))
        if set(agent_in_registry.get("tools", [])) != set(spec.get("tools", [])):
            update_fields["tools"] = spec.get("tools", [])
        if update_fields:
            registry.update_agent(reg_id, update_fields)
            print(f"[DEBUG-ACCEPT] Auto-applied changes to agent {reg_id}: {list(update_fields.keys())}", flush=True)

    if messenger:
        messenger.update_plan_status("approved")
        _tid = cl.user_session.get("current_team_id")
        await messenger.update_agents(registry, team_id=_tid)
        print(f"[DEBUG-ACCEPT] update_agents sent, registry has {len(registry.list_agents())} agents", flush=True)
        await messenger.clear_plan()
        await messenger.reply_notifications(team_id=_tid)

    # Update task status to running
    task_store = cl.user_session.get("task_store")
    current_task_id = cl.user_session.get("current_task_id")
    if task_store and current_task_id:
        task_store.update_task(current_task_id, status="running")
        await messenger.update_tasks(task_store, team_id=cl.user_session.get("current_team_id"))

    # Check if this is a create_agents plan (only create agents, don't run task)
    plan_type = cl.user_session.get("current_plan_type") or ""
    if plan_type == "create_agents":
        cl.user_session.set("state", STATE_IDLE)
        names = [s.get("name", "Agent") for s in registered_specs]
        if messenger:
            await messenger.reply(f"✅ สร้าง agent ในทีมแล้ว: {', '.join(names)}\n\nAgent เหล่านี้พร้อมใช้งาน — สั่งงานได้ทันทีโดยพิมพ์สิ่งที่ต้องการทำ")
            await messenger.reply_team_list(team_registry)
        cl.user_session.set("current_plan_type", None)
        return

    if messenger:
        await messenger.notify("🚀 กำลังเตรียม agents และเริ่มประมวลผล...")

    from backend.handlers.chat import execute_multi_agent_task
    await execute_multi_agent_task(user_input, registered_specs, registry)

    cl.user_session.set("attachment_context", None)
    cl.user_session.set("attachment_crewai_files", None)
    cl.user_session.set("last_attachments", [])
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
    rejected_specs = cl.user_session.get("current_agent_specs") or []
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_registry_id", None)

    # Capture user feedback from payload (frontend sends rejection reason)
    reject_feedback = ""
    if action.payload:
        reject_feedback = action.payload.get("feedback", "").strip()
    if not reject_feedback:
        reject_feedback = "ไม่ระบุเหตุผล"

    # Update task status — delete draft task or mark as rejected
    task_store = cl.user_session.get("task_store")
    current_task_id = cl.user_session.get("current_task_id")
    if task_store and current_task_id:
        task_store.delete_task(current_task_id)
        cl.user_session.set("current_task_id", None)
        if messenger:
            await messenger.update_tasks(task_store, team_id=cl.user_session.get("current_team_id"))

    if messenger:
        messenger.update_plan_status("rejected")
        await messenger.clear_plan()
        # Store rejected plan + user feedback in conversation history so AI can revise
        conversation_history = cl.user_session.get("conversation_history") or []
        if rejected_specs:
            plan_summary = json.dumps([
                {"name": a.get("name", ""), "role": a.get("role", ""), "task": a.get("task_description", "")}
                for a in rejected_specs
            ], ensure_ascii=False)
            conversation_history.append({"role": "assistant", "content": f"Proposed team: {plan_summary}"})
            conversation_history.append({"role": "user", "content": f"[REJECTED] {reject_feedback}"})
            cl.user_session.set("conversation_history", conversation_history)
        await messenger.reply(f"🔄 แผนงานถูกปฏิเสธ: {reject_feedback}\n\nกรุณาพิมพ์คำสั่งใหม่หรืออธิบายเพิ่มเติม — Manager จะสร้างแผนใหม่ที่ตรงตามความต้องการ")
        await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))


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
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
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
        "template_id": payload.get("template_id", ""),
        # Fallback to current_team_id — without this, agents created from MainLayout
        # or RetroDesktop (which don't send team_id) get team_id=None and disappear
        # from the UI on refresh, because update_agents filters by current_team_id
        "team_id": payload.get("team_id") or cl.user_session.get("current_team_id"),
    }

    try:
        new_agent = registry.add_agent(spec)

        # Register agent in team if team_id is provided
        team_id = spec.get("team_id")
        if team_id:
            team_registry = cl.user_session.get("team_registry")
            if team_registry:
                team_registry.add_agent(team_id, new_agent["id"])
                cl.user_session.set("team_registry", team_registry)
                if messenger:
                    await messenger.reply_team_list(team_registry)

        if messenger:
            _tid = cl.user_session.get("current_team_id")
            await messenger.update_agents(registry, team_id=_tid)
            await messenger.notify(f"✅ สร้าง Agent {new_agent['name']} สำเร็จ")
    except Exception as e:
        if messenger:
            await messenger.notify(f"❌ สร้าง Agent ไม่สำเร็จ: {str(e)}")


@cl.action_callback("edit_agent_form")
async def on_action_edit_agent_form(action: cl.Action):
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
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
        "template_id": payload.get("template_id", agent.get("template_id", "")),
    }

    try:
        registry.update_agent(agent_id, spec)
        if messenger:
            _tid = cl.user_session.get("current_team_id")
            await messenger.update_agents(registry, team_id=_tid)
            await messenger.notify(f"✅ แก้ไข Agent {agent_id} สำเร็จ")
    except Exception as e:
        if messenger:
            await messenger.notify(f"❌ แก้ไข Agent ไม่สำเร็จ: {str(e)}")


@cl.action_callback("delete_agent")
async def on_action_delete_agent(action: cl.Action):
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
    messenger = get_messenger()
    agent_id = action.payload.get("agent_id")
    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ที่ต้องการลบ")
        return

    if agent.get("is_manager"):
        if messenger:
            await messenger.notify("❌ ไม่สามารถลบ Manager ได้ — Manager เป็นส่วนสำคัญของทีม")
        return

    registry.delete_agent(agent_id)
    if messenger:
        _tid = cl.user_session.get("current_team_id")
        await messenger.update_agents(registry, team_id=_tid)


@cl.action_callback("assign_task_form")
async def on_action_assign_task_form(action: cl.Action):
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
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


@cl.action_callback("agent_feedback")
async def on_action_agent_feedback(action: cl.Action):
    """User gives feedback on agent's work — stored as learning."""
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
    messenger = get_messenger()
    payload = action.payload or {}
    agent_id = payload.get("agent_id")
    feedback_text = payload.get("feedback", "").strip()
    rating = payload.get("rating", "")

    if not agent_id or not feedback_text:
        if messenger:
            await messenger.notify("❌ ต้องระบุ agent_id และ feedback")
        return

    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent")
        return

    learning = {
        "type": "user_feedback",
        "lesson": feedback_text,
        "rating": rating,
        "timestamp": datetime.now().isoformat(),
    }
    registry.add_learning(agent_id, learning)

    if messenger:
        agent_name = agent.get("name", "Agent")
        await messenger.notify(f"📝 บันทึก feedback ให้ {agent_name} แล้ว — agent จะใช้ในการปรับปรุงครั้งต่อไป")


@cl.action_callback("confirm_tuning")
async def on_action_confirm_tuning(action: cl.Action):
    """Apply tuning proposal to agent registry — no auto re-run."""
    print("[DEBUG-CONFIRM-TUNING] on_action_confirm_tuning called", flush=True)
    user_id = cl.user_session.get("user_id")
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=user_id) if user_id else AgentRegistry()
        cl.user_session.set("registry", registry)
    messenger = get_messenger()
    proposals = cl.user_session.get("pending_tuning_proposal") or []
    # Fallback: use proposals from payload if session lost (e.g. after restart)
    if not proposals and action.payload:
        proposals = action.payload.get("proposals", [])
        if proposals:
            print(f"[DEBUG-CONFIRM-TUNING] Using proposals from payload (session was empty)", flush=True)
    print(f"[DEBUG-CONFIRM-TUNING] proposals={proposals}", flush=True)
    print(f"[DEBUG-CONFIRM-TUNING] registry agents: {[a.get('id') for a in registry.list_agents()]}", flush=True)

    if not proposals:
        if messenger:
            await messenger.notify("❌ ไม่พบ tuning proposal ที่รอยืนยัน")
        return

    applied_count = 0
    for proposal in proposals:
        agent_id = proposal.get("agent_id", "")
        changes = proposal.get("changes", [])
        if not agent_id or not changes:
            print(f"[DEBUG-CONFIRM-TUNING] Skipping proposal: agent_id={agent_id!r}, changes={len(changes)}", flush=True)
            continue

        agent = registry.get_by_id(agent_id)
        if not agent:
            print(f"[DEBUG-CONFIRM-TUNING] Agent not found: agent_id={agent_id!r}", flush=True)
            continue

        # Build update fields from changes
        update_fields = {}
        for change in changes:
            field = change.get("field", "")
            new_value = change.get("new_value", "")
            if not field:
                continue

            # Handle dot notation: personality.tone → nested dict
            if "." in field:
                parts = field.split(".")
                if parts[0] == "personality":
                    personality = dict(agent.get("personality", {}))
                    if len(parts) == 2:
                        personality[parts[1]] = new_value
                    update_fields["personality"] = personality
                elif parts[0] == "brand_context":
                    brand_context = dict(agent.get("brand_context", {}))
                    if len(parts) == 2:
                        brand_context[parts[1]] = new_value
                    update_fields["brand_context"] = brand_context
            else:
                # Direct field: persona, expertise, goal, etc.
                if field in ("persona", "backstory"):
                    update_fields["persona"] = new_value
                elif field == "expertise":
                    update_fields["expertise"] = new_value if isinstance(new_value, list) else [new_value]
                elif field == "tools":
                    update_fields["tools"] = new_value if isinstance(new_value, list) else [new_value]
                elif field in ("goal", "name", "role", "model", "team_id",
                               "template_id", "output_format", "quality_criteria"):
                    update_fields[field] = new_value
                elif field == "depends_on":
                    update_fields["depends_on"] = new_value if isinstance(new_value, list) else [new_value]
                elif field in ("review_iterations", "max_iter", "max_retry_limit"):
                    try:
                        update_fields[field] = int(new_value)
                    except (ValueError, TypeError):
                        pass
                elif field == "allow_delegation":
                    if isinstance(new_value, bool):
                        update_fields["allow_delegation"] = new_value
                    elif isinstance(new_value, str):
                        update_fields["allow_delegation"] = new_value.lower() in ("true", "1", "yes")

        if update_fields:
            registry.update_agent(agent_id, update_fields)
            applied_count += 1
            print(f"[DEBUG-CONFIRM-TUNING] Updated agent {agent_id}: fields={list(update_fields.keys())}", flush=True)

    print(f"[DEBUG-CONFIRM-TUNING] Applied {applied_count}/{len(proposals)} proposals", flush=True)
    cl.user_session.set("pending_tuning_proposal", None)

    if messenger:
        _tid = cl.user_session.get("current_team_id")
        await messenger.update_agents(registry, team_id=_tid)
        messenger.update_persisted_message("tuning_proposal", {"tuningStatus": "confirmed"})
        if applied_count > 0:
            await messenger.notify(f"✅ ปรับแต่ง agent แล้ว ({applied_count} agent) — พร้อมใช้งานในครั้งถัดไป")
        else:
            await messenger.notify("⚠️ ไม่สามารถปรับแต่งได้ — ตรวจสอบ agent_id และฟิลด์อีกครั้ง")
        await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))


@cl.action_callback("reject_tuning")
async def on_action_reject_tuning(action: cl.Action):
    """Reject tuning proposal — clear and return to idle."""
    messenger = get_messenger()
    cl.user_session.set("pending_tuning_proposal", None)
    if messenger:
        messenger.update_persisted_message("tuning_proposal", {"tuningStatus": "rejected"})
        await messenger.notify("❌ ยกเลิกการปรับแต่ง agent")
        await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))


# ============================================================
# Team Actions
# ============================================================

@cl.action_callback("create_team")
async def on_action_create_team(action: cl.Action):
    """Create a new team with a manager agent and optional worker agents."""
    messenger = get_messenger()
    payload = action.payload or {}
    name = payload.get("name", "").strip()
    description = payload.get("description", "").strip()
    manager_model = payload.get("manager_model", "auto")
    manager_persona = payload.get("manager_persona", "").strip()
    manager_goal = payload.get("manager_goal", "").strip()
    manager_expertise = payload.get("manager_expertise", [])
    manager_personality = payload.get("manager_personality", {})
    manager_brand_context = payload.get("manager_brand_context", {})
    agents_list = payload.get("agents", [])

    # Reset state — might be stuck in STATE_AWAITING_APPROVAL from AI modal flow
    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)

    if not name:
        if messenger:
            await messenger.notify("❌ ต้องระบุชื่อทีม")
        return

    team_registry = cl.user_session.get("team_registry") or TeamRegistry()
    team = team_registry.create_team(name=name, description=description, manager_model=manager_model)
    cl.user_session.set("team_registry", team_registry)

    # Create manager agent for this team
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
    default_goal = f"Coordinate the team '{name}' to accomplish user tasks efficiently. Plan work, delegate tasks, run independent tasks in parallel, and synthesize results."
    default_persona = "You are an experienced team manager who coordinates teams effectively. You know when tasks can run in parallel and when one must wait for another. You plan work, delegate tasks, and synthesize results to ensure quality."
    manager_agent = registry.add_agent({
        "name": f"{name} Manager",
        "role": "Manager",
        "goal": manager_goal or default_goal,
        "persona": manager_persona or default_persona,
        "model": manager_model if manager_model != "auto" else "",
        "tools": [],
        "team_id": team["id"],
        "is_manager": True,
        "expertise": manager_expertise,
        "personality": manager_personality,
        "brand_context": manager_brand_context,
    })
    team_registry.add_agent(team["id"], manager_agent["id"])

    # Create worker agents if provided
    created_agent_names = []
    for agent_entry in agents_list:
        agent_role = agent_entry.get("role", "").strip()
        if not agent_role:
            continue
        agent_spec = {
            "name": agent_entry.get("name", "").strip(),
            "role": agent_role,
            "goal": agent_entry.get("goal", "").strip(),
            "persona": agent_entry.get("persona", "").strip(),
            "tools": agent_entry.get("tools", []),
            "model": agent_entry.get("model", "").strip(),
            "team_id": team["id"],
            "template_id": agent_entry.get("template_id", ""),
            "expertise": agent_entry.get("expertise", []),
            "personality": agent_entry.get("personality", {}),
            "brand_context": agent_entry.get("brand_context", {}),
            "output_format": agent_entry.get("output_format", ""),
            "quality_criteria": agent_entry.get("quality_criteria", ""),
            "review_iterations": agent_entry.get("review_iterations", 0),
            "max_iter": agent_entry.get("max_iter", 0),
            "max_retry_limit": agent_entry.get("max_retry_limit", 0),
            "allow_delegation": agent_entry.get("allow_delegation", False),
        }
        new_agent = registry.add_agent(agent_spec)
        team_registry.add_agent(team["id"], new_agent["id"])
        created_agent_names.append(new_agent.get("name", "Agent"))

    cl.user_session.set("registry", registry)
    cl.user_session.set("team_registry", team_registry)
    # Switch current_team_id to the newly created team so its agents are visible
    cl.user_session.set("current_team_id", team["id"])

    if messenger:
        await messenger.reply_team_list(team_registry)
        await messenger.update_agents(registry, team_id=team["id"])
        agent_count = len(created_agent_names)
        if agent_count > 0:
            await messenger.notify(f"✅ สร้างทีม {team['name']} สำเร็จ — Manager + {agent_count} agent(s): {', '.join(created_agent_names)}")
        else:
            await messenger.notify(f"✅ สร้างทีม {team['name']} สำเร็จ")


@cl.action_callback("update_team")
async def on_action_update_team(action: cl.Action):
    """Update team settings."""
    messenger = get_messenger()
    payload = action.payload or {}
    team_id = payload.get("team_id", "")
    if not team_id:
        if messenger:
            await messenger.notify("❌ ไม่พบ Team ID")
        return

    team_registry = cl.user_session.get("team_registry") or TeamRegistry()
    fields = {}
    for key in ("name", "description", "manager_model"):
        if key in payload:
            fields[key] = payload[key]
    team_registry.update_team(team_id, fields)
    cl.user_session.set("team_registry", team_registry)

    if messenger:
        await messenger.reply_team_list(team_registry)
        await messenger.notify("✅ อัปเดตทีมสำเร็จ")


@cl.action_callback("delete_team")
async def on_action_delete_team(action: cl.Action):
    """Delete a team and all its agents and chat sessions."""
    messenger = get_messenger()
    team_id = action.payload.get("team_id", "")
    if not team_id:
        if messenger:
            await messenger.notify("❌ ไม่พบ Team ID")
        return

    team_registry = cl.user_session.get("team_registry") or TeamRegistry()
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)

    team = team_registry.get_team(team_id)
    if not team:
        if messenger:
            await messenger.notify("❌ ไม่พบทีมที่ต้องการลบ")
        return

    # Delete all agents belonging to this team (by team_id field as safety net)
    all_agents = registry.list_agents()
    for agent in all_agents:
        if agent.get("team_id") == team_id:
            registry.delete_agent(agent["id"])

    # Delete all chat sessions belonging to this team
    chat_store = cl.user_session.get("chat_store") or ChatStore(user_id=cl.user_session.get("user_id", "default"))
    chat_store.delete_sessions_by_team(team_id)

    # Delete all tasks belonging to this team
    task_store = cl.user_session.get("task_store") or TaskStore(user_id=cl.user_session.get("user_id", "default"))
    deleted_tasks = task_store.delete_tasks_by_team(team_id)
    print(f"[DEBUG-DELETE-TEAM] Deleted {deleted_tasks} tasks for team {team_id}", flush=True)

    # Delete all scheduled tasks belonging to this team
    from backend.agents.schedule_store import ScheduledTaskStore
    sched_store = ScheduledTaskStore(user_id=cl.user_session.get("user_id", "default"))
    deleted_sched = sched_store.delete_by_team(team_id)
    print(f"[DEBUG-DELETE-TEAM] Deleted {deleted_sched} scheduled tasks for team {team_id}", flush=True)

    team_registry.delete_team(team_id)
    cl.user_session.set("team_registry", team_registry)
    cl.user_session.set("registry", registry)

    # Reset current_team_id if we just deleted the active team — otherwise
    # update_agents filters by a non-existent team_id and the UI goes blank
    if cl.user_session.get("current_team_id") == team_id:
        cl.user_session.set("current_team_id", None)

    if messenger:
        await messenger.update_agents(registry, team_id=None)
        await messenger.reply_team_list(team_registry)
        await messenger.notify(f"🗑 ลบทีม {team.get('name', '')} และ agent, chat, task, งานตั้งเวลา ทั้งหมดแล้ว")


@cl.action_callback("delete_chat_session")
async def on_action_delete_chat_session(action: cl.Action):
    """Delete a chat session."""
    messenger = get_messenger()
    session_id = action.payload.get("session_id", "")
    if not session_id:
        if messenger:
            await messenger.notify("❌ ไม่พบ Session ID")
        return

    chat_store = cl.user_session.get("chat_store") or ChatStore(user_id=cl.user_session.get("user_id", "default"))
    chat_store.delete_session(session_id)

    # Delete only draft (pending) tasks from this session
    task_store = cl.user_session.get("task_store") or TaskStore(user_id=cl.user_session.get("user_id", "default"))
    draft_tasks = [t for t in task_store.get_tasks_by_session(session_id) if t.get("status") == "draft"]
    for t in draft_tasks:
        task_store.delete_task(t["id"])
    # Detach remaining tasks from the deleted session
    task_store.detach_tasks_by_session(session_id)

    if messenger:
        _tid = cl.user_session.get("current_team_id")
        await messenger.reply_chat_sessions(team_id=_tid)
        await messenger.update_tasks(task_store, team_id=_tid)
        await messenger.reply_notifications(team_id=_tid)
        # Switch to another session
        current_team_id = cl.user_session.get("current_team_id")
        remaining = chat_store.list_sessions(team_id=current_team_id, include_unassigned=True) if current_team_id else chat_store.list_sessions()
        if remaining:
            messenger.current_session_id = remaining[0]["id"]
        else:
            new_s = chat_store.create_session("New Chat", team_id=current_team_id)
            messenger.current_session_id = new_s["id"]
        await messenger.reply_chat_history(messenger.current_session_id)
        if draft_tasks:
            await messenger.notify(f"🗑 ลบแชทและ {len(draft_tasks)} task ที่รอดำเนินการแล้ว")
        else:
            await messenger.notify("🗑 ลบแชทแล้ว")


@cl.action_callback("config_agent")
async def on_action_config_agent(action: cl.Action):
    """Update agent configuration from modal."""
    messenger = get_messenger()
    payload = action.payload or {}
    agent_id = payload.get("agent_id", "")
    if not agent_id:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ID")
        return

    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent")
        return

    fields = {}
    for key in ("name", "role", "goal", "persona", "model", "tools", "expertise",
                "personality", "brand_context", "template_id", "depends_on",
                "output_format", "quality_criteria", "review_iterations",
                "max_iter", "max_retry_limit", "allow_delegation"):
        if key in payload:
            fields[key] = payload[key]

    if fields:
        registry.update_agent(agent_id, fields)
        if messenger:
            _tid = cl.user_session.get("current_team_id")
            await messenger.update_agents(registry, team_id=_tid)
            await messenger.notify(f"✅ อัปเดต {agent.get('name', 'Agent')} แล้ว")


@cl.action_callback("refresh_credits")
async def on_action_refresh_credits(action: cl.Action):
    """Refresh credit balance from OpenRouter and send updated platform state."""
    messenger = get_messenger()
    if messenger:
        await messenger._send(trigger="refresh")


@cl.action_callback("fetch_history")
async def on_action_fetch_history(action: cl.Action):
    """Send task history logs to frontend."""
    messenger = get_messenger()
    if messenger:
        await messenger.reply_history(team_id=cl.user_session.get("current_team_id"))
