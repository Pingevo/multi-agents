import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Rocket, Pencil, Trash2, Bot } from "lucide-react";

export default function AgentConsole() {
  const { agents = [] } = props;
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const openAdd = () => {
    setModal('add');
    setForm({ name: '', role: '', goal: '', persona: '', tools: '' });
  };

  const openEdit = (agent) => {
    setModal('edit');
    setForm({
      agent_id: agent.id,
      name: agent.name || '',
      role: agent.role || '',
      goal: agent.goal || '',
      persona: agent.persona || '',
      tools: (agent.tools || []).join(', '),
    });
  };

  const openAssign = (agent) => {
    setModal('assign');
    setForm({ agent_id: agent.id, task: '' });
  };

  const submit = () => {
    if (modal === 'add') {
      callAction({ name: 'add_agent_form', payload: form });
    } else if (modal === 'edit') {
      callAction({ name: 'edit_agent_form', payload: form });
    } else if (modal === 'assign') {
      callAction({ name: 'assign_task_form', payload: form });
    }
    setModal(null);
  };

  const handleDelete = (agentId) => {
    if (confirm('ยืนยันการลบ Agent นี้?')) {
      callAction({ name: 'delete_agent', payload: { agent_id: agentId } });
    }
  };

  const handleChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const statusColor = (status) => {
    return status === 'Idle' ? 'bg-green-500 hover:bg-green-500' : 'bg-red-500 hover:bg-red-500';
  };

  return (
    <div className="w-full h-full flex flex-col gap-4 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <h2 className="text-lg font-bold">Agent Console</h2>
        </div>
        <Button size="sm" onClick={openAdd}>
          <Plus className="h-4 w-4 mr-1" /> Add
        </Button>
      </div>

      <Separator />

      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead className="w-20">Status</TableHead>
              <TableHead className="w-32">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {agents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                  ยังไม่มี Agent
                </TableCell>
              </TableRow>
            ) : (
              agents.map((agent) => (
                <TableRow key={agent.id}>
                  <TableCell className="font-mono text-xs">{agent.id}</TableCell>
                  <TableCell className="font-medium">{agent.name}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{agent.role}</TableCell>
                  <TableCell>
                    <Badge className={statusColor(agent.status)}>{agent.status}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        onClick={() => openAssign(agent)}
                        title="Assign Task"
                      >
                        <Rocket className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        onClick={() => openEdit(agent)}
                        title="Edit"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-destructive"
                        onClick={() => handleDelete(agent.id)}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={!!modal} onOpenChange={() => setModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {modal === 'add' && 'Add Agent'}
              {modal === 'edit' && 'Edit Agent'}
              {modal === 'assign' && 'Assign Task'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3 py-2">
            {(modal === 'add' || modal === 'edit') && (
              <>
                <div className="space-y-1">
                  <Label>Name</Label>
                  <Input value={form.name || ''} onChange={(e) => handleChange('name', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Role</Label>
                  <Input value={form.role || ''} onChange={(e) => handleChange('role', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Goal</Label>
                  <Input value={form.goal || ''} onChange={(e) => handleChange('goal', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Persona</Label>
                  <Input value={form.persona || ''} onChange={(e) => handleChange('persona', e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Tools (comma separated)</Label>
                  <Input value={form.tools || ''} onChange={(e) => handleChange('tools', e.target.value)} placeholder="search_web, ..." />
                </div>
              </>
            )}

            {modal === 'assign' && (
              <div className="space-y-1">
                <Label>Task Description</Label>
                <textarea
                  className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.task || ''}
                  onChange={(e) => handleChange('task', e.target.value)}
                  placeholder="พิมพ์รายละเอียดงานที่ต้องการให้ Agent ทำ..."
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setModal(null)}>Cancel</Button>
            <Button onClick={submit}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
