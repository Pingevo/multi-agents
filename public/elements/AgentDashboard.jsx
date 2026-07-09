import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Bot, CheckCircle, XCircle, AlertCircle, Loader2 } from "lucide-react";

export default function AgentDashboard() {
  const { tasks = [], current_plan = null, notifications = [] } = props;

  const statusIcon = (status) => {
    switch (status) {
      case 'complete': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'error': return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running': return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      default: return <Bot className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const statusVariant = (status) => {
    switch (status) {
      case 'complete': return 'default';
      case 'error': return 'destructive';
      case 'running': return 'secondary';
      default: return 'outline';
    }
  };

  return (
    <div className="w-full h-full flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Agent Control Panel</h2>
          <p className="text-sm text-muted-foreground">Dashboard หลักสำหรับติดตามงานและแผน Agent</p>
        </div>
      </div>

      <Separator />

      {notifications.length > 0 && (
        <div className="space-y-2">
          {notifications.map((n, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
              <AlertCircle className="h-4 w-4" />
              <span>{n}</span>
            </div>
          ))}
        </div>
      )}

      {current_plan && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">แผนงานที่รอการอนุมัติ</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="font-medium">Agent:</span> {current_plan.agent?.name || '-'}</div>
              <div><span className="font-medium">Role:</span> {current_plan.agent?.role || '-'}</div>
              <div className="col-span-2"><span className="font-medium">Task:</span> {current_plan.task_description || '-'}</div>
              <div className="col-span-2"><span className="font-medium">Tools:</span> {(current_plan.agent?.tools || []).join(', ') || '-'}</div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => callAction({ name: 'accept_plan', payload: {} })}>✅ Accept</Button>
              <Button size="sm" variant="outline" onClick={() => callAction({ name: 'reject_plan', payload: {} })}>✏️ Reject</Button>
              <Button size="sm" variant="destructive" onClick={() => callAction({ name: 'cancel_plan', payload: {} })}>❌ Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex-1">
        <h3 className="text-sm font-semibold mb-2">Task Slots</h3>
        <ScrollArea className="h-full">
          <div className="grid grid-cols-1 gap-4 pr-4">
            {tasks.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  ยังไม่มีงานที่กำลังรัน กรุณาพิมพ์คำสั่งในแชทหรือกด Assign จาก Agent Console
                </CardContent>
              </Card>
            ) : (
              tasks.map((task) => (
                <Card key={task.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {statusIcon(task.status)}
                        <CardTitle className="text-base">{task.title}</CardTitle>
                      </div>
                      <Badge variant={statusVariant(task.status)}>{task.status}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Agent: {task.agent || '-'}</span>
                      <span className="font-medium">{task.progress}%</span>
                    </div>
                    <Progress value={task.progress} className="h-2" />
                    {task.result && (
                      <div className="text-sm whitespace-pre-wrap bg-muted p-3 rounded-md max-h-64 overflow-y-auto">
                        {task.result}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
