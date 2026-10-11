'use strict';
let adminKey = '';
let selected = '';
const el = id => document.getElementById(id);
const labels = {active:'البوت شغال',human_required:'مراجعة بشرية',resolved:'مغلقة'};
const showError = error => { el('error').textContent = error ? String(error.message || error) : ''; };
async function api(path, body) {
  const response = await fetch(path, {method:body===undefined?'GET':'POST',headers:{'X-Admin-Key':adminKey,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
  const data = await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
}
function node(tag,text,css){const n=document.createElement(tag);n.textContent=text;if(css)n.className=css;return n;}
async function refresh(){
  const status=el('filter').value;
  const rows=await api('/admin/conversations'+(status?'?status='+encodeURIComponent(status):''));
  el('list').replaceChildren();
  if(!rows.length) el('list').append(node('p','مفيش محادثات في الحالة دي. ابعت رسالة للرقم التجريبي أو اختار كل المحادثات.','muted'));
  for(const row of rows){
    const b=node('button',row.phone+' · '+labels[row.status]);
    b.onclick=()=>load(row.phone).catch(showError);el('list').append(b);
  }
  if(selected) await load(selected);
}
async function load(phone){
  const data=await api('/admin/conversations/'+encodeURIComponent(phone));
  selected=phone;const c=data.conversation;const box=el('detail');box.replaceChildren();
  box.append(node('h2',phone),node('p',labels[c.status]+' · '+new Date(c.updated_at*1000).toLocaleString()));
  const link=node('a','افتح wa.me من حساب واتساب الشخصي');link.href=c.wa_link;link.target='_blank';link.rel='noopener noreferrer';box.append(link);
  box.append(node('p',c.summary||'لسه مفيش ملخص.','summary'));
  box.append(node('p','مصدر الملخص: '+(c.summary_source||'—')+' | آخر خطأ: '+(c.last_error||'—'),'muted'));
  const actions=node('div','','row');
  for(const [action,label] of [['pause','تحويل لموظف'],['resume','تشغيل البوت'],['resolve','إغلاق المحادثة']]){
    const b=node('button',label,'secondary');b.onclick=async()=>{b.disabled=true;showError('');try{await api('/admin/conversations/'+phone+'/'+action,{});await refresh();}catch(e){showError(e);b.disabled=false;}};actions.append(b);
  }box.append(actions);
  for(const m of data.messages){
    const item=node('div','','message '+m.direction);
    item.append(node('small',new Date(m.timestamp*1000).toLocaleString()+' · '+m.actor+' · '+m.type+' · '+m.state+(m.error?' · '+m.error:'')));
    item.append(document.createTextNode(m.text||(m.type==='audio'?'[فويس محفوظ كـmedia ID بدون تفريغ]':'[بدون نص]')));box.append(item);
  }
  const text=document.createElement('textarea');text.placeholder='اكتب ردك اليدوي… هيتبعت من رقم Meta ويوقف البوت.';text.maxLength=3000;text.setAttribute('aria-label','الرد اليدوي');box.append(text);
  const send=node('button','إرسال الرد');send.onclick=async()=>{if(!text.value.trim())return;send.disabled=true;showError('');try{await api('/admin/conversations/'+phone+'/reply',{text:text.value});await refresh();}catch(e){showError(e);send.disabled=false;}};box.append(send);
}
el('connect').onclick=async()=>{showError('');adminKey=el('key').value.trim();try{const config=await api('/admin/config');el('config').textContent=config.missing.length?'إعدادات ناقصة: '+config.missing.join(', '):'الإعدادات مكتملة محليًا. نجاح الربط يتأكد برسالة واتساب فعلية.';el('workspace').hidden=false;el('login').hidden=true;el('key').value='';await refresh();}catch(e){adminKey='';showError(e);}};
el('logout').onclick=()=>{adminKey='';selected='';el('workspace').hidden=true;el('login').hidden=false;el('list').replaceChildren();el('detail').replaceChildren();el('config').textContent='';showError('');};
el('refresh').onclick=()=>{showError('');refresh().catch(showError);};
el('filter').onchange=()=>refresh().catch(showError);
