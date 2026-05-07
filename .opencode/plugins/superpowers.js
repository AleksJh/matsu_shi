const path = require('path');
const { execSync } = require('child_process');

const SKILLS_DIR = path.resolve(__dirname, '../../skills');

let skillsRegistered = false;

function registerSkills() {
  if (skillsRegistered) return;
  
  try {
    execSync(`opencode skills add ${SKILLS_DIR}`, { 
      stdio: 'ignore',
      cwd: __dirname
    });
    skillsRegistered = true;
  } catch (e) {
    console.warn('Failed to register skills:', e.message);
  }
}

function injectBootstrapMessage(messages) {
  if (messages.length === 0) return messages;
  
  const firstUserMessage = messages.find(m => m.role === 'user');
  if (!firstUserMessage) return messages;
  
  const bootstrapContent = `Superpowers Tool Mapping:
- TodoWrite → todowrite
- Task with subagents → @mention system
- Skill tool → native skill tool
- File operations (Read, Write, Edit, Bash) → native OpenCode tools

Available skills are registered in the skills directory.`;

  if (typeof firstUserMessage.content === 'string') {
    firstUserMessage.content = bootstrapContent + '\n\n' + firstUserMessage.content;
  } else if (Array.isArray(firstUserMessage.content)) {
    firstUserMessage.content.unshift({
      type: 'text',
      text: bootstrapContent
    });
  }
  
  return messages;
}

module.exports = {
  name: 'superpowers',
  hooks: {
    config: registerSkills,
    'experimental.chat.messages.transform': injectBootstrapMessage
  }
};
