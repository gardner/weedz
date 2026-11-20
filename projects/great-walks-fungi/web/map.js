import {geoMercator, geoPath} from 'd3-geo';
import {select} from 'd3-selection';
import {zoom, zoomIdentity} from 'd3-zoom';

const data = JSON.parse(document.getElementById('fungi-data').textContent);
const $ = id => document.getElementById(id);
const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const fmt = new Intl.NumberFormat('en-NZ');
let active = data.walks[0].id;
let month = 0;
let transform = zoomIdentity;
const svg = select('#map-svg');
const width = 700, height = 740;
const projection = geoMercator().fitExtent([[70,35],[width-70,height-35]], data.basemap);
const path = geoPath(projection);
const layer = svg.append('g');
layer.append('g').attr('class','land').selectAll('path').data(data.basemap.features).join('path').attr('d',path);
const routes = layer.append('g').selectAll('path').data(data.walks).join('path').attr('class','route').attr('d',w=>path(w.geometry));
const leaders = svg.append('g').attr('class','marker-leaders').selectAll('line').data(data.walks).join('line');
const markers = svg.append('g').selectAll('g').data(data.walks).join('g').attr('class','marker')
  .attr('role','button').attr('tabindex',0).attr('aria-label',w=>`${w.name}: ${peak(w)}`)
  .on('click',(_,w)=>choose(w.id)).on('keydown',(event,w)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose(w.id);}});
markers.append('circle').attr('class','hit').attr('r',18);
markers.append('circle').attr('class','dot').attr('r',6);
markers.append('text').attr('class','marker-index').attr('text-anchor','middle').attr('dy','0.35em').text((_,i)=>i+1);
const zoomer = zoom().scaleExtent([1,14]).on('zoom',event=>{transform=event.transform;layer.attr('transform',transform);placeMarkers();});
svg.call(zoomer).on('dblclick.zoom',null);
function point(w){return projection(w.center);}
function placeMarkers(){
 const pixelScale=svg.node().getBoundingClientRect().width/width;
 const positions=data.walks.map(w=>{const p=transform.apply(point(w));return {x:p[0]*pixelScale,y:p[1]*pixelScale};});
 for(let iteration=0;iteration<16;iteration++){
  for(let i=0;i<positions.length;i++)for(let j=i+1;j<positions.length;j++){
   const a=positions[i],b=positions[j],dx=b.x-a.x,dy=b.y-a.y,distance=Math.hypot(dx,dy);
   if(distance<27){const shift=(27-distance)/2,ux=distance?dx/distance:1,uy=distance?dy/distance:0;a.x-=ux*shift;a.y-=uy*shift;b.x+=ux*shift;b.y+=uy*shift;}
  }
 }
 markers.attr('transform',(w,i)=>`translate(${positions[i].x/pixelScale},${positions[i].y/pixelScale}) scale(${1/pixelScale})`);
 leaders.attr('x1',w=>transform.apply(point(w))[0]).attr('y1',w=>transform.apply(point(w))[1])
  .attr('x2',(_,i)=>positions[i].x/pixelScale).attr('y2',(_,i)=>positions[i].y/pixelScale);
}
new ResizeObserver(placeMarkers).observe(svg.node());
function peak(w){return w.peak_months.length ? w.peak_months.map(m=>months[m-1]).join(' / ') : 'No eligible records';}
function season(w){
 const seasons=new Set(w.peak_months.map(p=>Math.floor((p%12)/3)));
 return seasons.size===1 ? `season-${[...seasons][0]}` : 'season-none';
}
function choose(id){active=id;render();}
function render(){
 const w = data.walks.find(w=>w.id===active);
 $('walk-select').value=active;
 $('selected-name').textContent=w.name;
 $('mode').textContent=w.mode==='Paddling'?'River journey · paddling':'Walking track';
 $('peak-month').textContent=peak(w);
 $('record-count').textContent=fmt.format(w.total);
 $('year-coverage').textContent=`${w.years.length} of ${data.last_year-data.first_year+1} years represented`;
 $('scope').textContent=`Within ${data.radius_km} km of the sourced route`;
 $('sample-note').textContent=w.total<30||w.years.length<3?'Limited sample — do not treat this peak as a reliable recommendation.':'Recorded activity, not a forecast of mushroom abundance.';
 const max = Math.max(...w.counts,1);
 const bars=$('month-bars');bars.replaceChildren();
 months.forEach((name,i)=>{
  const button=document.createElement('button');button.type='button';button.className='month-bar';button.setAttribute('aria-label',`${name}: ${w.counts[i]} observations, ${w.observer_days[i]} observer-days`);
  button.setAttribute('aria-pressed',String(month===i+1));button.onclick=()=>{month=month===i+1?0:i+1;render();};
  const label=document.createElement('span');label.className='month-label';label.textContent=name.slice(0,3);
  const track=document.createElement('span');track.className='bar-track';const fill=document.createElement('span');fill.className='bar-fill';fill.style.width=`${100*w.counts[i]/max}%`;track.append(fill);
  if(w.peak_months.includes(i+1))button.classList.add('peak');
  const value=document.createElement('span');value.className='bar-number';value.textContent=fmt.format(w.counts[i]);button.append(label,track,value);bars.append(button);
 });
 $('selected-month').textContent=month?`${months[month-1]} · ${fmt.format(w.counts[month-1])} records · ${fmt.format(w.observer_days[month-1])} observer-days`:'Choose a month to compare recorded activity across walks.';
 $('map-month').textContent=month?`${months[month-1]} records`:'Peak recorded month';
 $('clear-month').hidden=!month;
 $('doc-link').href=w.url;
 $('query-link').href=w.query_url;
 markers.attr('class',w=>`marker ${season(w)} ${w.id===active?'selected':''}`).attr('aria-pressed',w=>String(w.id===active));
 routes.attr('class',w=>`route ${w.id===active?'selected':''}`);
 markers.select('.dot').attr('r',w=>month?5+12*Math.sqrt(w.counts[month-1]/Math.max(1,...data.walks.map(x=>x.counts[month-1]))):9);
 $('walk-list').replaceChildren();
 data.walks.forEach((walk,i)=>{
  const button=document.createElement('button');button.type='button';button.className=`walk-row ${walk.id===active?'selected':''}`;button.setAttribute('aria-pressed',String(walk.id===active));button.onclick=()=>choose(walk.id);
  const index=document.createElement('span');index.className='walk-index';index.textContent=i+1;
  const name=document.createElement('span');name.className='walk-name';name.textContent=walk.name.replace(' Track','');
  const result=document.createElement('span');result.className='walk-value';result.textContent=month?fmt.format(walk.counts[month-1]):walk.peak_months.map(m=>months[m-1].slice(0,3)).join('/');
  button.append(index,name,result);$('walk-list').append(button);
 });
 placeMarkers();
}
$('walk-select').replaceChildren(...data.walks.map(w=>{const o=document.createElement('option');o.value=w.id;o.textContent=w.name;return o;}));
$('walk-select').onchange=event=>choose(event.target.value);
$('clear-month').onclick=()=>{month=0;render();};
$('zoom-in').onclick=()=>svg.call(zoomer.scaleBy,1.5);
$('zoom-out').onclick=()=>svg.call(zoomer.scaleBy,1/1.5);
$('zoom-reset').onclick=()=>svg.call(zoomer.transform,zoomIdentity);
$('all-records').textContent=fmt.format(data.unique_observations);
$('period').textContent=`${data.first_year}–${data.last_year}`;
$('generated').textContent=data.generated_at.slice(0,10);
$('header-radius').textContent=`${data.radius_km} km`;
$('method-radius').textContent=data.radius_km;
$('method-first').textContent=`1 January ${data.first_year}`;
$('method-last').textContent=`31 December ${data.last_year}`;
render();
window.fungiMap = {getState:()=>({active,month,zoom:transform.k}), selectWalk:choose};
