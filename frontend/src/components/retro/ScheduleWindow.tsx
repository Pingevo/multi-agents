export const ScheduleWindow: React.FC = () => {
  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-line bg-cream">
        <span className="text-[11px] font-bold text-ink">Schedule</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3.5 flex flex-col gap-2">
        <div className="bg-paper border border-line rounded-retro p-3">
          <div className="text-[11px] font-bold text-ink mb-1.5">Upcoming Tasks</div>
          <div className="text-[10px] text-ink-3">No scheduled tasks. Schedule functionality will be available soon.</div>
        </div>
        <div className="bg-paper border border-line rounded-retro p-3">
          <div className="text-[11px] font-bold text-ink mb-1.5">Recurring Jobs</div>
          <div className="text-[10px] text-ink-3">No recurring jobs configured.</div>
        </div>
      </div>
    </div>
  );
};
