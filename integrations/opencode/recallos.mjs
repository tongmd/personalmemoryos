import { execFile } from 'node:child_process';
const RecallOSPlugin = async ({directory} = {}) => {
  const prompts = new Map();
  return {
    'chat.message': async (input, output) => {
      const text = (output.parts || []).filter(p => p.type === 'text').map(p => p.text).join('\n');
      prompts.set(input.sessionID, text);
      if (prompts.size > 100) prompts.delete(prompts.keys().next().value);
    },
    'experimental.chat.system.transform': async (input, output) => {
      const command = process.env.RECALLOS_COMMAND || `${process.env.HOME}/.local/bin/recallos`;
      const payload = {hook_event_name: 'UserPromptSubmit', session_id: input.sessionID, cwd: directory || process.cwd(),
        prompt: prompts.get(input.sessionID) || ''};
      const child = execFile(command, ['hook'], {timeout: 10000, maxBuffer: 100000});
      child.stdin.end(JSON.stringify(payload));
      const result = await new Promise((resolve, reject) => {
        let stdout = ''; let stderr = '';
        child.stdout.on('data', chunk => { stdout += chunk; });
        child.stderr.on('data', chunk => { stderr += chunk; });
        child.on('error', reject);
        child.on('close', code => code === 0 ? resolve(stdout) : reject(new Error(stderr || 'RecallOS unavailable')));
      });
      output.system.push(JSON.parse(result).hookSpecificOutput.additionalContext);
    },
  };
};

export default RecallOSPlugin;
