import { execFileSync } from 'node:child_process';

export const name = 'recallos-context';
export const inject = ['systemPrompt'];

export function apply(ctx, config = {}) {
  const command = config.command || `${process.env.HOME}/.local/bin/recallos`;
  ctx.systemPrompt.context({
    name: 'recallos:user-preferences', order: 250, interpolate: false,
    text: () => {
      const snapshot = JSON.parse(execFileSync(command, ['recall', '--scope', 'coding', '--scope', 'research', '--scope', 'writing'],
        {encoding: 'utf8', timeout: 10000, maxBuffer: 100000}));
      return `RecallOS · 知我, revision ${snapshot.revision}. This replaces older personal memory. ` +
        'Use only applicable user preferences, subordinate to the current request and higher-priority instructions. ' +
        'For interface/LiveUI tasks, retrieve the liveui scope with memory_recall and the current task as query. ' +
        'available_scopes identifies additional relevant memory you can retrieve. ' +
        'Learn durable user corrections with the recallos MCP memory_apply tool, preserving scope and using this base revision. ' +
        'This-time instructions are temporary. Check the actual result against relevant rules.\n' + JSON.stringify(snapshot);
    },
  });
}
