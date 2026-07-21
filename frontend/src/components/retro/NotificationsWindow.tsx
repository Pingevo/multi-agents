import type { ChatMessage } from '../chatTypes';

interface NotificationsWindowProps {
  chatMessages: ChatMessage[];
  onAcceptPlan?: () => void;
  onRejectPlan?: () => void;
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onRetryImage?: (approvalId: string) => void;
  onApproveAgentResult?: (reviewId: string) => void;
  onRejectAgentResult?: (reviewId: string) => void;
  onSkipReview?: (agentName: string) => void;
  onConfirmTuning?: (proposals?: any[]) => void;
  onRejectTuning?: () => void;
}

export const NotificationsWindow: React.FC<NotificationsWindowProps> = ({
  chatMessages,
  onAcceptPlan,
  onRejectPlan,
  onApproveImage,
  onRejectImage,
  onRetryImage,
  onApproveAgentResult,
  onRejectAgentResult,
  onSkipReview,
  onConfirmTuning,
  onRejectTuning,
}) => {
  const pendingPlans = chatMessages.filter(m => m.messageType === 'plan' && m.planStatus === 'pending');
  const pendingImages = chatMessages.filter(m => m.messageType === 'image_approval' && (m.approvalStatus === 'pending' || m.approvalStatus === 'error'));
  const pendingReviews = chatMessages.filter(m => m.messageType === 'agent_review' && m.reviewStatus === 'pending');
  const pendingTuning = chatMessages.filter(m => m.messageType === 'tuning_proposal' && m.tuningStatus !== 'confirmed' && m.tuningStatus !== 'rejected');

  const totalCount = pendingPlans.length + pendingImages.length + pendingReviews.length + pendingTuning.length;

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2.5">
        {totalCount === 0 && (
          <div className="flex items-center justify-center h-full text-[11px] text-ink-3">
            ✅ ไม่มีรายการรออนุมัติ
          </div>
        )}

        {/* Pending Plans */}
        {pendingPlans.map((plan) => (
          <div key={plan.id} className="bg-paper border border-line rounded-retro p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">📋</span>
              <span className="text-[11px] font-bold text-ink">Plan Approval</span>
            </div>
            <div className="text-[10px] text-ink-2 mb-1">
              {plan.planTaskDescription || plan.content?.slice(0, 80) || 'Plan awaiting approval'}
            </div>
            {plan.planAgents && (
              <div className="text-[10px] text-ink-3 mb-2">
                {plan.planAgents.length} agents · {plan.planType || 'new'}
              </div>
            )}
            <div className="flex gap-1.5">
              <button
                className="text-[10px] px-2.5 py-1.5 border border-red bg-paper text-red rounded-retro-sm font-bold hover:bg-red hover:text-white transition-colors"
                onClick={() => onRejectPlan?.()}
              >
                ปฏิเสธ
              </button>
              <button
                className="text-[10px] px-2.5 py-1.5 border border-green bg-paper text-green rounded-retro-sm font-bold hover:bg-green hover:text-white transition-colors"
                onClick={() => onAcceptPlan?.()}
              >
                อนุมัติแผน
              </button>
            </div>
          </div>
        ))}

        {/* Pending Image Approvals */}
        {pendingImages.map((img) => (
          <div key={img.id} className="bg-paper border border-line rounded-retro p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">🖼️</span>
              <span className="text-[11px] font-bold text-ink">Image Generation</span>
            </div>
            {img.approvalStatus === 'error' ? (
              <>
                <div className="text-[10px] text-red mb-2">⚠ {img.imageError || 'Generation error'}</div>
                <button
                  className="text-[10px] px-2.5 py-1.5 border border-amber bg-paper text-amber rounded-retro-sm font-bold hover:bg-amber hover:text-white transition-colors"
                  onClick={() => onRetryImage?.(img.approvalId || '')}
                >
                  🔄 Retry
                </button>
              </>
            ) : (
              <>
                <div className="text-[10px] text-ink-2 mb-1">Prompt: {img.imagePrompt || '—'}</div>
                {img.agentName && <div className="text-[10px] text-ink-3 mb-2">Agent: {img.agentName}</div>}
                <div className="flex gap-1.5">
                  <button
                    className="text-[10px] px-2.5 py-1.5 border border-red bg-paper text-red rounded-retro-sm font-bold hover:bg-red hover:text-white transition-colors"
                    onClick={() => onRejectImage?.(img.approvalId || '')}
                  >
                    Reject
                  </button>
                  <button
                    className="text-[10px] px-2.5 py-1.5 border border-green bg-paper text-green rounded-retro-sm font-bold hover:bg-green hover:text-white transition-colors"
                    onClick={() => onApproveImage?.(img.approvalId || '')}
                  >
                    Generate
                  </button>
                </div>
              </>
            )}
          </div>
        ))}

        {/* Pending Agent Reviews */}
        {pendingReviews.map((review) => (
          <div key={review.id} className="bg-paper border border-line rounded-retro p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">🔍</span>
              <span className="text-[11px] font-bold text-ink">Agent Review</span>
            </div>
            <div className="text-[10px] text-ink-2 mb-1">Agent: {review.agentName || '—'}</div>
            {review.agentRole && <div className="text-[10px] text-ink-3 mb-2">Role: {review.agentRole}</div>}
            <div className="flex gap-1.5">
              <button
                className="text-[10px] px-2.5 py-1.5 border border-line-2 bg-paper text-ink-2 rounded-retro-sm font-bold hover:bg-cream-2 transition-colors"
                onClick={() => onSkipReview?.(review.agentName || '')}
              >
                Skip
              </button>
              <button
                className="text-[10px] px-2.5 py-1.5 border border-red bg-paper text-red rounded-retro-sm font-bold hover:bg-red hover:text-white transition-colors"
                onClick={() => onRejectAgentResult?.(review.reviewId || '')}
              >
                Reject
              </button>
              <button
                className="text-[10px] px-2.5 py-1.5 border border-green bg-paper text-green rounded-retro-sm font-bold hover:bg-green hover:text-white transition-colors"
                onClick={() => onApproveAgentResult?.(review.reviewId || '')}
              >
                Approve
              </button>
            </div>
          </div>
        ))}

        {/* Pending Tuning Proposals */}
        {pendingTuning.map((tuning) => (
          <div key={tuning.id} className="bg-paper border border-line rounded-retro p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">🔧</span>
              <span className="text-[11px] font-bold text-ink">Tuning Proposal</span>
            </div>
            {tuning.tuningProposals && (
              <div className="text-[10px] text-ink-2 mb-2">
                {tuning.tuningProposals.length} change(s) proposed for {tuning.tuningProposals[0]?.agent_name || 'agent'}
              </div>
            )}
            <div className="flex gap-1.5">
              <button
                className="text-[10px] px-2.5 py-1.5 border border-red bg-paper text-red rounded-retro-sm font-bold hover:bg-red hover:text-white transition-colors"
                onClick={() => onRejectTuning?.()}
              >
                Reject
              </button>
              <button
                className="text-[10px] px-2.5 py-1.5 border border-green bg-paper text-green rounded-retro-sm font-bold hover:bg-green hover:text-white transition-colors"
                onClick={() => onConfirmTuning?.(tuning.tuningProposals)}
              >
                Confirm
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
