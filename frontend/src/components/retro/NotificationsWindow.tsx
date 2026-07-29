import React, { useState } from 'react';
import type { NotificationItem } from '../chatTypes';

type FilterTab = 'pending' | 'completed';

interface NotificationsWindowProps {
  notifications: NotificationItem[];
  onNavigate: (sessionId: string, windowId: 'chat' | 'tasks') => void;
}

const isPending = (n: NotificationItem): boolean => {
  if (n.messageType === 'plan') return n.planStatus === 'pending';
  if (n.messageType === 'image_approval') return n.approvalStatus === 'pending' || n.approvalStatus === 'error';
  if (n.messageType === 'agent_review') return n.reviewStatus === 'pending';
  if (n.messageType === 'tuning_proposal') return n.tuningStatus !== 'confirmed' && n.tuningStatus !== 'rejected';
  return false;
};

const isCompleted = (n: NotificationItem): boolean => {
  if (n.messageType === 'plan') return n.planStatus === 'approved' || n.planStatus === 'rejected';
  if (n.messageType === 'image_approval') return n.approvalStatus === 'approved' || n.approvalStatus === 'rejected';
  if (n.messageType === 'agent_review') return n.reviewStatus === 'approved' || n.reviewStatus === 'rejected';
  if (n.messageType === 'tuning_proposal') return n.tuningStatus === 'confirmed' || n.tuningStatus === 'rejected';
  return false;
};

const getTargetWindow = (_n: NotificationItem): 'chat' | 'tasks' => {
  return 'chat';
};

const getIcon = (n: NotificationItem): string => {
  if (n.messageType === 'plan') return '📋';
  // Type-aware icon — without this, all media approvals show 🖼️ even for TTS/STT/Vision
  if (n.messageType === 'image_approval') {
    const mt = n.mediaType || 'image';
    if (mt === 'video') return '🎬';
    if (mt === 'tts') return '🔊';
    if (mt === 'stt') return '📝';
    if (mt === 'vision') return '�️';
    return '�🖼️';
  }
  if (n.messageType === 'agent_review') return '🔍';
  if (n.messageType === 'tuning_proposal') return '🔧';
  return '🔔';
};

const getTitle = (n: NotificationItem): string => {
  if (n.messageType === 'plan') return 'Plan Approval';
  // Type-aware title — without this, all media approvals say 'Image Generation'
  if (n.messageType === 'image_approval') {
    const mt = n.mediaType || 'image';
    if (mt === 'video') return 'Video Generation';
    if (mt === 'tts') return 'Text-to-Speech';
    if (mt === 'stt') return 'Audio Transcription';
    if (mt === 'vision') return 'Vision Analysis';
    return 'Image Generation';
  }
  if (n.messageType === 'agent_review') return 'Agent Review';
  if (n.messageType === 'tuning_proposal') return 'Tuning Proposal';
  return 'Notification';
};

const getDescription = (n: NotificationItem): string => {
  if (n.messageType === 'plan') return n.planTaskDescription || n.content?.slice(0, 80) || 'Plan awaiting approval';
  if (n.messageType === 'image_approval') return n.imagePrompt || 'Image generation request';
  if (n.messageType === 'agent_review') return `Agent: ${n.agentName || '—'}`;
  if (n.messageType === 'tuning_proposal') return n.tuningProposals ? `${n.tuningProposals.length} change(s) for ${n.tuningProposals[0]?.agent_name || 'agent'}` : 'Tuning proposal';
  return n.content?.slice(0, 80) || '';
};

const getStatusBadge = (n: NotificationItem): { text: string; color: string } => {
  if (n.messageType === 'plan') {
    if (n.planStatus === 'approved') return { text: '✅ อนุมัติ', color: 'text-green' };
    if (n.planStatus === 'rejected') return { text: '❌ ปฏิเสธ', color: 'text-red' };
    return { text: '⏳ รอดำเนินการ', color: 'text-amber' };
  }
  if (n.messageType === 'image_approval') {
    if (n.approvalStatus === 'approved') return { text: '✅ อนุมัติ', color: 'text-green' };
    if (n.approvalStatus === 'rejected') return { text: '❌ ยกเลิก', color: 'text-red' };
    if (n.approvalStatus === 'error') return { text: '⚠️ ผิดพลาด', color: 'text-red' };
    return { text: '⏳ รอดำเนินการ', color: 'text-amber' };
  }
  if (n.messageType === 'agent_review') {
    if (n.reviewStatus === 'approved') return { text: '✅ อนุมัติ', color: 'text-green' };
    if (n.reviewStatus === 'rejected') return { text: '❌ ปฏิเสธ', color: 'text-red' };
    return { text: '⏳ รอดำเนินการ', color: 'text-amber' };
  }
  if (n.messageType === 'tuning_proposal') {
    if (n.tuningStatus === 'confirmed') return { text: '✅ ยืนยัน', color: 'text-green' };
    if (n.tuningStatus === 'rejected') return { text: '❌ ยกเลิก', color: 'text-red' };
    return { text: '⏳ รอดำเนินการ', color: 'text-amber' };
  }
  return { text: '', color: '' };
};

const formatTime = (ts: number): string => {
  const diff = Date.now() - ts;
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const mins = Math.floor(diff / (1000 * 60));
  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (mins > 0) return `${mins}m ago`;
  return 'just now';
};

export const NotificationsWindow: React.FC<NotificationsWindowProps> = ({
  notifications,
  onNavigate,
}) => {
  const [activeTab, setActiveTab] = useState<FilterTab>('pending');

  const pending = notifications.filter(isPending);
  const completed = notifications.filter(isCompleted);
  const displayList = activeTab === 'pending' ? pending : completed;

  return (
    <div className="h-full flex flex-col">
      {/* Filter tabs */}
      <div className="flex gap-1 p-2 border-b border-line bg-cream">
        <button
          className={`text-[10px] px-3 py-1.5 rounded-retro-sm font-bold transition-colors ${
            activeTab === 'pending' ? 'bg-ink text-paper' : 'bg-paper text-ink-2 hover:bg-cream-2'
          }`}
          onClick={() => setActiveTab('pending')}
        >
          รอดำเนินการ ({pending.length})
        </button>
        <button
          className={`text-[10px] px-3 py-1.5 rounded-retro-sm font-bold transition-colors ${
            activeTab === 'completed' ? 'bg-ink text-paper' : 'bg-paper text-ink-2 hover:bg-cream-2'
          }`}
          onClick={() => setActiveTab('completed')}
        >
          ดำเนินการแล้ว ({completed.length})
        </button>
      </div>

      {/* Notification list */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2.5">
        {displayList.length === 0 && (
          <div className="flex items-center justify-center h-full text-[11px] text-ink-3">
            {activeTab === 'pending' ? '✅ ไม่มีรายการรอดำเนินการ' : 'ไม่มีรายการที่ดำเนินการแล้ว'}
          </div>
        )}

        {displayList.map((n) => {
          const badge = getStatusBadge(n);
          const targetWindow = getTargetWindow(n);
          return (
            <div
              key={n.id}
              className="bg-paper border border-line rounded-retro p-3 cursor-pointer hover:border-ink-2 transition-colors"
              onClick={() => onNavigate(n.sessionId, targetWindow)}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-base">{getIcon(n)}</span>
                <span className="text-[11px] font-bold text-ink flex-1">{getTitle(n)}</span>
                <span className={`text-[9px] font-bold ${badge.color}`}>{badge.text}</span>
              </div>
              <div className="text-[10px] text-ink-2 mb-1">
                {getDescription(n)}
              </div>
              <div className="flex items-center justify-between text-[9px] text-ink-3">
                <span>💬 {n.sessionTitle || 'Unknown session'}</span>
                <span>{formatTime(n.timestamp)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
