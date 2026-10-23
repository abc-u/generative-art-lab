let curriculum=[];
let phases=[];
const phaseGrid=document.querySelector("#phase-grid");
const lessonList=document.querySelector("#lesson-list");
function renderCurriculum(query=""){
  if(!phaseGrid||!lessonList)return;
  phaseGrid.innerHTML=phases.map(p=>`<article class="phase-card ${p.id===1?"active":""}"><span class="phase-number">PHASE 0${p.id}</span><span class="phase-range">${p.range}</span><h3>${p.name}</h3><p>${p.desc}</p></article>`).join("");
  const filtered=curriculum.filter(d=>`${d.day} ${d.title} ${d.topic} ${d.description}`.toLowerCase().includes(query.toLowerCase()));
  lessonList.innerHTML=filtered.map(({day,title,topic,description,phase,status})=>`<a class="lesson-row ${status==="published"?"is-available":""}" href="./lesson.html?day=${day}&v=2" ${status!=="published"?'aria-label="学習計画：Day '+day+' '+title+'"':''}><span class="day-number">DAY ${String(day).padStart(2,"0")}</span><div><h3>${title}</h3><p>${description}</p></div><span class="phase-tag">PHASE 0${phase} · ${topic}</span><span class="row-action">${status==="published"?"OPEN ↗":"PLANNED ···"}</span></a>`).join("")||'<p class="curriculum-footnote">該当するレッスンはありません。</p>';
  document.querySelector("#archive-count").textContent=String(filtered.length).padStart(2,"0");
}
fetch("./curriculum.json").then(response=>response.json()).then(data=>{curriculum=data.lessons;phases=data.phases;renderCurriculum(search?.value||"")}).catch(()=>{});
const search=document.querySelector("#lesson-search");
if(search)search.addEventListener("input",()=>renderCurriculum(search.value));
document.addEventListener("keydown",event=>{if(event.key==="/"&&!/INPUT|TEXTAREA/.test(document.activeElement.tagName)){event.preventDefault();search?.focus();}});
function mulberry32(a){return()=>{let t=a+=0x6D2B79F5;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return((t^t>>>14)>>>0)/4294967296}}
function drawPreview(canvas,seed=42,large=false){if(!canvas)return;const ctx=canvas.getContext("2d");const rect=canvas.getBoundingClientRect();const dpr=Math.min(window.devicePixelRatio||1,2);canvas.width=Math.max(1,rect.width*dpr);canvas.height=Math.max(1,rect.height*dpr);ctx.scale(dpr,dpr);const w=rect.width,h=rect.height;ctx.fillStyle=large?"#cfc5af":"#e9e1d1";ctx.fillRect(0,0,w,h);const rnd=mulberry32(seed);const cols=large?12:18,rows=large?12:15,cw=w/cols,ch=h/rows;for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){const cx=x*cw+cw/2,cy=y*ch+ch/2;const dx=(rnd()-.5)*Math.min(cw,ch)*.48,dy=(rnd()-.5)*Math.min(cw,ch)*.48;const s=Math.min(cw,ch)*(.35+rnd()*.31);ctx.save();ctx.translate(cx+dx,cy+dy);ctx.rotate((rnd()-.5)*.6);ctx.fillStyle=(x+y)%5===0?"#c95d42":(x+y)%3===0?"#4f6252":"#34352e";ctx.fillRect(-s/2,-s/2,s,s);ctx.restore()}}
let previewSeed=72;const heroArt=document.querySelector("#hero-art");const lessonArt=document.querySelector("#lesson-art");
function drawPreviews(){drawPreview(heroArt,previewSeed,false);drawPreview(lessonArt,12,true)}
document.querySelector("#hero-regenerate")?.addEventListener("click",()=>{previewSeed++;drawPreviews()});
window.addEventListener("resize",drawPreviews);requestAnimationFrame(drawPreviews);
const galleryCanvases=[...document.querySelectorAll(".gallery-art")];
function drawGallery(canvas,seed){if(!canvas)return;const ctx=canvas.getContext("2d"),r=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.max(1,r.width*dpr);canvas.height=Math.max(1,r.height*dpr);ctx.scale(dpr,dpr);const w=r.width,h=r.height,kind=canvas.dataset.kind,random=mulberry32(seed);ctx.fillStyle="#e8dfcc";ctx.fillRect(0,0,w,h);const cols=11,rows=8,cw=w/cols,ch=h/rows;for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){const size=Math.min(cw,ch)*(kind==="order"?.58:.48+random()*.16),x=col*cw+cw/2+(kind==="drift"?(random()-.5)*cw*.28:0),y=row*ch+ch/2+(kind==="drift"?(random()-.5)*ch*.28:0);ctx.save();ctx.translate(x,y);ctx.rotate(kind==="drift"?(random()-.5)*.4:0);ctx.fillStyle=(row+col)%7===0?"#c95d42":(row+col)%3===0?"#596a54":"#34352e";if(kind==="orbit"){ctx.beginPath();ctx.arc(0,0,size*.52,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#e8dfcc";ctx.lineWidth=1.3;ctx.beginPath();ctx.arc(0,0,size*.22,0,Math.PI*2);ctx.stroke()}else ctx.fillRect(-size/2,-size/2,size,size);ctx.restore()}}
function renderGallery(){galleryCanvases.forEach((canvas,index)=>drawGallery(canvas,112+index*31))}
renderGallery();window.addEventListener("resize",renderGallery);
document.querySelectorAll(".gallery-refresh").forEach(button=>button.addEventListener("click",()=>{const canvas=button.closest(".gallery-card")?.querySelector("canvas");if(canvas)drawGallery(canvas,Math.floor(Math.random()*100000))}));
