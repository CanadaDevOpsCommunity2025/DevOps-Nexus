const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const chatWindow = document.getElementById('chat-window');
const modelNameEl = document.getElementById('model-name');
const modelSelect = document.getElementById('model-select');
const applyModelBtn = document.getElementById('apply-model');
const toolListEl = document.getElementById('tool-list');

function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = `${role}: ${text}`;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if(!message) return;
  appendMessage('user', message);
  input.value='';
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message})
    });
    const data = await res.json();
    if(data.error){
      appendMessage('system', 'Error: '+data.error);
    } else {
      appendMessage('assistant', data.reply);
    }
  } catch(err){
    appendMessage('system', 'Network error');
  }
});

async function loadModels(){
  try {
    const res = await fetch('/api/models');
    const data = await res.json();
    if(data.models){
      modelSelect.innerHTML = '';
      data.models.slice(0,40).forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.name;
        opt.textContent = m.name;
        modelSelect.appendChild(opt);
      });
    } else if(data.error){
      modelSelect.innerHTML = `<option>Error loading models</option>`;
    }
  } catch(e){
    modelSelect.innerHTML = `<option>Failed to load models</option>`;
  }
}

async function switchModel(){
  const val = modelSelect.value;
  if(!val) return;
  applyModelBtn.disabled = true;
  try {
    const res = await fetch('/api/model', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({model_name: val})});
    const data = await res.json();
    if(data.ok){
      modelNameEl.textContent = data.model;
      appendMessage('system', `Model switched to ${data.model}`);
    } else if(data.error){
      appendMessage('system', `Model switch failed: ${data.error}`);
    }
  } catch(e){
    appendMessage('system', 'Network error switching model');
  } finally {
    applyModelBtn.disabled = false;
  }
}

applyModelBtn?.addEventListener('click', (e)=>{ e.preventDefault(); switchModel(); });

async function loadTools(){
  try {
    const res = await fetch('/api/tools');
    const data = await res.json();
    if(data.tools){
      toolListEl.innerHTML = '';
      data.tools.forEach(t => {
        const li = document.createElement('li');
        li.textContent = t;
        li.className = 'tool-item';
        li.title = 'Click to insert /tool command';
        li.addEventListener('click', ()=>{
          input.value = `/tool ${t} `;
          input.focus();
        });
        toolListEl.appendChild(li);
      });
    }
  } catch(e){
    toolListEl.innerHTML = '<li>Error loading tools</li>';
  }
}

// Initial loads
loadModels();
loadTools();