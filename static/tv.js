(() => {
 const content=document.getElementById("tv-content"), feedback=document.getElementById("tv-feedback");
 let paused=window.matchMedia('(prefers-reduced-motion: reduce)').matches, loading=false;
 const pauseButton=document.getElementById('tv-pause');
 function showPause(){
   pauseButton.textContent=paused?'Reanudar actualizaciones':'Pausar actualizaciones';
   pauseButton.setAttribute('aria-pressed',String(paused));
   feedback.textContent=paused?'Actualizaciones y rotación pausadas.':'Actualización cada 20 segundos · hasta 2 tareas por columna';
 }
 showPause();
 document.getElementById("tv-pause").addEventListener("click", event=>{
   paused=!paused; showPause();
 });
 document.getElementById("tv-fullscreen").addEventListener("click", async()=>{
   try { if(document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); }
   catch { feedback.textContent="No se pudo activar pantalla completa. Puedes utilizar F11."; }
 });
 async function refresh(){
   if(paused || loading || document.hidden || content.contains(document.activeElement)) return;
   loading=true;
   const marker=document.getElementById("tv-page");
   const current=Number(marker?.dataset.page||1), total=Number(marker?.dataset.pages||1);
   const next=paused?current:current%total+1;
   const url=new URL(content.dataset.url,location.href); url.searchParams.set("page",next);
   const abort=new AbortController(), timeout=setTimeout(()=>abort.abort(),15000);
   try{
     const response=await fetch(url,{headers:{"X-Requested-With":"XMLHttpRequest"},credentials:"same-origin",signal:abort.signal});
     if(!response.ok || response.redirected || response.headers.get("X-Turno-Fragment")!=="tv") throw new Error();
     const html=await response.text();
     if(paused || content.contains(document.activeElement)) return;
     content.innerHTML=html;
     feedback.textContent=paused?"Rotación pausada · datos actualizados":"Actualización cada 20 segundos · hasta 2 tareas por columna";
   }catch{feedback.textContent="Sin actualización: revisa la conexión o la sesión. Los datos mostrados pueden estar desactualizados.";}
   finally{clearTimeout(timeout); loading=false;}
 }
 setInterval(refresh,20000);
 document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
})();
