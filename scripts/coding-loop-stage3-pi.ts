/** Native Pi hook transport. Enabled only by the reviewed Stage 3 wrapper. */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';

export default function (pi: ExtensionAPI) {
  const helper = fileURLToPath(new URL('./_coding_loop_live_native.py', import.meta.url));
  function send(event: Record<string, unknown>, ctx: any) {
    const run = process.env.SUPER_STAGE3_RUN;
    if (!run) throw new Error('Stage 3 admission state is missing');
    const reply = spawnSync(process.env.SUPER_STAGE3_PYTHON || 'python3', [helper, 'hook', run], {
      input: JSON.stringify({ ...event, cwd: ctx.cwd,
        session_id: ctx.sessionManager.getSessionId(),
        model: ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined,
        effort: pi.getThinkingLevel() }),
      encoding: 'utf8', timeout: 6000,
    });
    if (reply.error || reply.status !== 0) throw new Error('Stage 3 admission denied: ' + (reply.stdout || reply.error?.message));
    return reply.stdout.trim() ? JSON.parse(reply.stdout) : {};
  }
  pi.on('session_start', (_event, ctx) => {
    send({ hook_event_name: 'SessionStart' }, ctx);
    send({ hook_event_name: 'SubagentStart', agent_id: ctx.sessionManager.getSessionId() }, ctx);
  });
  pi.on('before_agent_start', (event, ctx) => {
    const response = send({ hook_event_name: 'SessionStart' }, ctx);
    return { systemPrompt: event.systemPrompt + '\n' + (response.hookSpecificOutput?.additionalContext || '') };
  });
  pi.on('tool_call', (event, ctx) => {
    try {
      const response = send({ hook_event_name: 'PreToolUse', tool_name: event.toolName,
        tool_use_id: event.toolCallId, tool_input: event.input }, ctx);
      if (response.hookSpecificOutput?.updatedInput) Object.assign(event.input, response.hookSpecificOutput.updatedInput);
    } catch (error) { return { block: true, terminate: true, reason: String(error) }; }
  });
  pi.on('tool_result', (event, ctx) => {
    send({ hook_event_name: 'PostToolUse', tool_name: event.toolName,
      tool_use_id: event.toolCallId, tool_input: event.input,
      tool_response: { details: event.details, content: event.content, isError: event.isError } }, ctx);
  });
  pi.on('agent_settled', (_event, ctx) => {
    const last = ctx.sessionManager.getBranch().filter((entry: any) => entry.type === 'message' && entry.message.role === 'assistant').at(-1);
    const text = last?.message.content?.filter((part: any) => part.type === 'text').map((part: any) => part.text).join('\n');
    send({ hook_event_name: 'SubagentStop', agent_id: ctx.sessionManager.getSessionId(), last_assistant_message: text }, ctx);
  });
}
