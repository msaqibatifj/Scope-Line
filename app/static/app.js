const $=id=>document.getElementById(id);
let session=crypto.randomUUID(),count=0;

function message(role,text){
  $('messages').querySelector('.empty-state')?.remove();
  const item=document.createElement('article');
  item.className=role;
  item.textContent=role+': '+text;
  $('messages').append(item);
  item.scrollIntoView({block:'nearest'});
}

function setRunState(kind,text){
  $('status').textContent=text;
  $('run-dot').className='run-dot '+kind;
}

function selectTab(name){
  // Step 1: show one workspace view and keep tab accessibility state in sync.
  for(const tabName of ['chat','context']){
    const selected=tabName===name;
    $(tabName+'-tab').classList.toggle('active',selected);
    $(tabName+'-tab').setAttribute('aria-selected',String(selected));
    $(tabName+'-tab').tabIndex=selected?0:-1;
    $(tabName+'-panel').hidden=!selected;
  }
}

async function init(){
  try{
    const response=await fetch('/models');
    if(!response.ok)throw Error('Models unavailable');
    const data=await response.json();
    for(const model of data.models){
      const option=document.createElement('option');
      option.value=model;
      option.textContent=model;
      option.selected=model===data.default;
      $('model').append(option);
    }
    const readiness=data.readiness||{};
    $('model-readiness').textContent=readiness.ready
      ? 'Live model ready: '+readiness.configured_default
      : 'Degraded mode: '+(readiness.reason||'live model unavailable')+(readiness.fallback_enabled ? '. Fallback: '+(readiness.fallback_model||'local-scripted') : '. Fallback disabled.');
  }catch(error){
    $('status').textContent=error.message;
    $('send').disabled=true;
  }
}

for(const name of ['chat','context']){
  $(name+'-tab').onclick=()=>selectTab(name);
  $(name+'-tab').onkeydown=event=>{
    if(!['ArrowLeft','ArrowRight'].includes(event.key))return;
    event.preventDefault();
    const next=name==='chat'?'context':'chat';
    selectTab(next);
    $(next+'-tab').focus();
  };
}

$('external').oninput=()=>{
  $('context-count').textContent=$('external').value.length.toLocaleString()+' / 10,000';
};

$('chat').onsubmit=async event=>{
  event.preventDefault();
  const task=$('task').value.trim();
  if(!task)return;
  const context=$('external').value.trim();
  message('user',task);
  $('send').disabled=true;
  $('reset').disabled=true;
  setRunState('running','Reviewing agreement evidence…');
  $('trace').textContent='Waiting for result...';
  $('observations').textContent='Waiting for result...';
  try{
    // Step 2: send pasted context separately so the agent treats it as untrusted data.
    const response=await fetch('/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        session_id:session,
        task,
        model:$('model').value,
        external_context:context?[{source:'pasted-context',content:context,trust:'untrusted'}]:[],
      }),
    });
    const data=await response.json();
    if(!response.ok)throw Error(JSON.stringify(data.detail));
    message('agent',data.final_response);
    count+=2;
    $('memory').textContent=count+' messages exchanged; server retains a configured bounded history';
    setRunState(data.status==='completed'?'success':(data.status==='blocked'||data.status==='failed'||data.status==='contract_error'?'error':'idle'),data.status.replaceAll('_',' ')+' · '+data.stop_reason.replaceAll('_',' ')+' · '+data.steps+' steps');
    const fallback=data.events.find(event=>event.event==='provider_fallback');
    if(fallback)$('status').textContent+=' · degraded: '+fallback.reason;
    $('trace').textContent=JSON.stringify(data.tool_calls,null,2);
    $('observations').textContent=JSON.stringify(data.events,null,2);
    $('task').value='';
  }catch(error){
    setRunState('error','Request error: '+error.message);
  }finally{
    $('send').disabled=false;
    $('reset').disabled=false;
  }
};

$('reset').onclick=async()=>{
  try{
    const response=await fetch('/chat/'+session,{method:'DELETE'});
    if(!response.ok)throw Error('Reset failed');
    // Step 3: a new review clears conversation, context, and execution evidence.
    session=crypto.randomUUID();
    count=0;
    $('messages').replaceChildren();
    $('memory').textContent='0 messages in this review';
    $('external').value='';
    $('context-count').textContent='0 / 10,000';
    $('task').value='';
    setRunState('idle','Ready for a new review');
    $('trace').textContent='No tool calls yet.';
    $('observations').textContent='No observations yet.';
    selectTab('chat');
  }catch(error){
    $('status').textContent=error.message;
  }
};

selectTab('chat');
for(const button of document.querySelectorAll('.example')){
  button.onclick=()=>{ $('task').value=button.dataset.task; $('task').focus(); };
}
init();
