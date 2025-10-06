const tg = window.Telegram.WebApp;
tabs.forEach(t=>t.addEventListener('click',()=>switchTab(t.dataset.tab)));
let currentAction=null;

function showMainButton(text){tg.MainButton.setText(text);tg.MainButton.show();}
function hideMainButton(){tg.MainButton.hide();}
tg.onEvent('mainButtonClicked',()=>{
if(!currentAction)return;
const payload={restaurant:RESTAURANT,action:currentAction.type,data:currentAction.payload};
tg.sendData(JSON.stringify(payload));
});

function switchTab(name){
tabs.forEach(t=>t.classList.toggle('active',t.dataset.tab===name));
if(name==='menu')renderMenu();
if(name==='booking')renderBooking();
if(name==='about')renderAbout();
}

function renderMenu(){
hideMainButton();
content.innerHTML='';
MENU_ITEMS.forEach(item=>{
const el=document.createElement('div');
el.className='card';
el.innerHTML=`<div class="dish-title"><strong>${item.name}</strong><span class="small">${item.price} ₽</span></div><div class="dish-desc">${item.desc}</div><div style="margin-top:10px"><a class="btn" href="#" data-id="${item.id}" data-name="${item.name}">Забронировать</a></div>`;
content.appendChild(el);
});
content.querySelectorAll('a.btn').forEach(a=>{
a.addEventListener('click',e=>{
e.preventDefault();
currentAction={type:'book_dish',payload:{dish_id:a.dataset.id,dish_name:a.dataset.name}};
showMainButton(`Забронировать: ${a.dataset.name}`);
});
});
}

function renderBooking(){
content.innerHTML='';
const form=document.createElement('div');
form.className='card';
form.innerHTML=`<label>На сколько человек?</label><input id="inp_people" type="number" min="1" value="2"><label>Дата и время (ДД.MM.ГГГГ ЧЧ:ММ)</label><input id="inp_dt" placeholder="25.10.2025 19:30"><label>Телефон</label><input id="inp_phone" placeholder="+7..."><label>Комментарий (опционально)</label><textarea id="inp_comment" rows="3"></textarea>`;
content.appendChild(form);
const updatePayload=()=>{
const people=parseInt(document.getElementById('inp_people').value||1);
const dt=document.getElementById('inp_dt').value||'';
const phone=document.getElementById('inp_phone').value||'';
const comment=document.getElementById('inp_comment').value||'';
currentAction={type:'booking_form',payload:{people,datetime:dt,phone,comment}};
showMainButton('Отправить бронь');
};
['inp_people','inp_dt','inp_phone','inp_comment'].forEach(id=>{
document.addEventListener('input',e=>{if(e.target.id===id)updatePayload();});
});
updatePayload();
}

function renderAbout(){
hideMainButton();
content.innerHTML='';
const box=document.createElement('div');
box.className='card';
box.innerHTML=`<h3>О ресторане ${RESTAURANT}</h3><p class="small">Уютная атмосфера, лучшие продукты и забота о каждом госте. Открой меню или забронируй стол прямо из этого приложения.</p>`;
content.appendChild(box);
}

switchTab('menu');