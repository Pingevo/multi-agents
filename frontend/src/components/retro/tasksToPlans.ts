import type { Task, Agent } from '../../types/platform';
import type { PlanData, PlanAgentData } from './types';

const agentIcon = (name: string): string => {
  const n = name.toLowerCase();
  if (n.includes('analyst') || n.includes('product')) return '📊';
  if (n.includes('copy') || n.includes('writer')) return '✍️';
  if (n.includes('image') || n.includes('design') || n.includes('visual')) return '🎨';
  if (n.includes('seo') || n.includes('search')) return '🔍';
  if (n.includes('manager')) return '🧠';
  return '🤖';
};

const mapStatus = (status: string): PlanAgentData['stat'] => {
  if (status === 'complete' || status === 'done') return 'done';
  if (status === 'running') return 'running';
  if (status === 'error') return 'waiting';
  return 'idle';
};

const statusText = (status: string): string => {
  if (status === 'complete' || status === 'done') return 'เสร็จแล้ว';
  if (status === 'running') return 'กำลังทำงาน';
  if (status === 'error') return 'ข้อผิดพลาด';
  return 'รอคิว';
};

export const tasksToPlans = (tasks: Task[], agents: Agent[]): PlanData[] => {
  if (!tasks || tasks.length === 0) return [];

  return tasks.map(task => {
    const taskAgents: PlanAgentData[] = task.agent_progress && task.agent_progress.length > 0
      ? task.agent_progress.map(ap => ({
          ic: agentIcon(ap.name),
          name: ap.name,
          stat: mapStatus(ap.status),
          statText: statusText(ap.status),
          output: ap.output || '',
          model: undefined,
          duration: undefined,
        }))
      : agents.filter(a => !a.is_manager).map(a => ({
          ic: agentIcon(a.name),
          name: a.name,
          stat: mapStatus(task.status),
          statText: statusText(task.status),
          output: task.result || '',
        }));

    const doneCount = taskAgents.filter(a => a.stat === 'done').length;
    const progress = taskAgents.length > 0
      ? Math.round((doneCount / taskAgents.length) * 100)
      : task.progress || 0;

    const status = task.status === 'complete' ? 'done' : task.status === 'running' ? 'running' : task.status === 'stopped' ? 'done' : 'pending';
    const statusTextVal = status === 'done' ? (task.status === 'stopped' ? 'หยุดแล้ว' : 'เสร็จสิ้น') : status === 'running' ? 'กำลังทำงาน' : 'รออนุมัติ';

    return {
      id: task.id,
      ic: '📋',
      title: task.title,
      status: status as PlanData['status'],
      statusText: statusTextVal,
      progress,
      agents: taskAgents,
    };
  });
};
