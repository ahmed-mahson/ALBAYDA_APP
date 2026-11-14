'use strict';
const form=document.querySelector('#login');
const message=document.querySelector('#message');
let native=null;
function normalizeDigits(value){return value.replace(/[٠-٩۰-۹]/g,char=>String(char.charCodeAt(0)-(char>='۰'?'۰':'٠').charCodeAt(0)));}
function updateStatus(status){document.querySelector('#saved').hidden=!status.saved;document.querySelector('#biometric').hidden=!status.biometricSaved;document.querySelector('#forget').hidden=!status.saved;}
function nativeReady(){native=window.AlbaydaAndroid;if(!native)return;document.querySelector('#device-options').hidden=false;document.querySelector('#native-actions').hidden=false;native.getStatus().then(updateStatus).catch(error=>message.textContent=error.message);}
window.addEventListener('albayda-native-ready',nativeReady);
window.addEventListener('albayda-native-status',event=>updateStatus(event.detail));
nativeReady();
async function authenticate(password){const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});const data=await response.json();if(!response.ok)throw Error(data.error||'تعذر تسجيل الدخول.');}
async function operation(task){const buttons=document.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);message.textContent='';try{await task();}catch(error){message.textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false);}}
form.onsubmit=event=>{event.preventDefault();operation(async()=>{const password=normalizeDigits(form.elements.password.value);const remember=Boolean(native&&form.elements.remember.checked);const name=form.elements.device_name.value.trim();if(remember&&(name.length<3||!/^[0-9]{12,128}$/.test(password)))throw Error('لحفظ الدخول، أدخل اسمًا من ثلاثة أحرف على الأقل وكلمة مرور رقمية من 12 إلى 128 رقمًا.');await authenticate(password);if(remember){try{await native.saveCredentials({name,password});}catch(error){message.textContent=error.message;}}location.replace('/');});};
for(const [id,method] of [['saved','loginWithSaved'],['biometric','loginWithBiometric']])document.querySelector('#'+id).onclick=()=>operation(async()=>{const credentials=await native[method]();await authenticate(credentials.password);location.replace('/');});
document.querySelector('#forget').onclick=()=>operation(async()=>{await native.forgetCredentials();updateStatus(await native.getStatus());message.textContent='تم نسيان بيانات الدخول على هذا الهاتف.';});
