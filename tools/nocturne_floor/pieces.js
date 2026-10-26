// Nocturne's original furniture, using the Vegas renderer's materials and canvas helpers.
// All dimensions are game pixels; renderAll paints at 2x for smooth material detail.
const originalRailEW = PIECES.rail_glass_ew;
for (const key of Object.keys(PIECES)) delete PIECES[key];

// One collision shape per run keeps the navigation bake clear of repeated seams.
def('rail_front', {
  name: 'Nocturne continuous glass rail (192)', cat: 'Decor',
  size: [196,26], anchor: [98,24], body: [-96,-3,192,4],
  draw(g) {
    for(let i=0;i<3;i++) {g.save();g.translate(i*64,0);originalRailEW.draw(g);g.restore();}
  }
});
def('rail_side', {
  name: 'Nocturne continuous glass rail (320)', cat: 'Decor',
  size: [14,340], anchor: [7,338], body: [-2,-320,4,320],
  draw(g) {
    g.fillStyle='rgba(185,221,228,.28)';g.fillRect(5,2,4,336);
    metalV(g,5.8,18,2.4,320);metalV(g,5.5,1,3,320);
    for(let y=18;y<=338;y+=64) {
      metalV(g,5,y-18,4,18);
      g.fillStyle='rgba(250,255,255,.5)';g.fillRect(5,y-17,.7,17);
    }
    g.fillStyle='rgba(250,255,255,.55)';g.fillRect(6.4,2,.7,318);
  }
});

def('signature', {
  name: 'Nocturne illuminated signature', cat: 'Wall decor', mount: 'wall',
  size: [400, 60], anchor: [200, 60], body: null,
  draw(g) {
    fillRR(g, 1, 1, 398, 57, 3, '#10191c');
    g.save(); rr(g, 2, 2, 396, 55, 3); g.clip();
    g.fillStyle = tex(g, 'marble_black', .45); g.globalAlpha = .35; g.fillRect(2, 2, 396, 55); g.restore();
    for (let x = 14; x < 388; x += 8) {
      metalV(g, x, 7, 1, 44, BRASS);
    }
    fillRR(g, 63, 7, 274, 43, 2, '#111b1e');
    label(g, 'N O C T U R N E', 200, 25, 21, '#f1dfb7', {font: FONT.deco, glow: 3});
    label(g, 'L A S   V E G A S   ·   P R I V A T E   S A L O N', 200, 43, 6.5, '#cfae73');
    ledLine(g, 14, 56, 386, 56, .6, LED, 5);
  }
});

def('banquette', {
  name: 'Nocturne velvet banquette', cat: 'Seating', size: [148, 66], anchor: [74, 62],
  body: [-65, -25, 130, 24],
  draw(g) {
    shade(g, 74, 61, 71, 5, .5);
    for (const x of [13, 131]) metalV(g, x, 51, 3, 11, BRASS);
    fillRR(g, 7, 9, 134, 48, 14, '#071a1d');
    fillRR(g, 8, 5, 132, 30, 13, lin(g, 0, 5, 0, 35, [[0,'#466264'],[.24,'#28484c'],[1,'#122f34']]));
    for (let x = 19; x < 139; x += 11) {
      g.strokeStyle = 'rgba(6,22,26,.45)'; g.lineWidth = .7;
      g.beginPath(); g.moveTo(x, 11); g.lineTo(x, 32); g.stroke();
      g.fillStyle = 'rgba(177,209,198,.14)'; g.fillRect(x+1, 11, .7, 19);
    }
    fillRR(g, 18, 31, 112, 22, 7, lin(g, 0, 31, 0, 54, [[0,'#426165'],[.5,'#2b484d'],[1,'#18343a']]));
    for (const x of [55, 93]) { g.fillStyle = '#1c393e'; g.fillRect(x, 34, .7, 16); }
    fillRR(g, 5, 25, 13, 29, 6, '#254247'); fillRR(g, 130, 25, 13, 29, 6, '#254247');
    ledLine(g, 17, 56, 131, 56, .5, '#cba86e', 2);
    grain(g, 20, 34, 108, 16, 222, .028);
  }
});

def('cocktail', {
  name: 'Nocturne marble cocktail table', cat: 'Tables & desks', size: [64, 54], anchor: [32, 51],
  body: [-21, -13, 42, 13],
  draw(g) {
    shade(g, 33, 49, 29, 4, .5); metalV(g, 27, 28, 10, 21, BRASS);
    fillEll(g, 32, 48, 18, 3, lin(g, 14, 0, 50, 0, BRASS));
    fillEll(g, 32, 27, 28, 13, '#70542b');
    g.save(); ell(g,32,24,28,13); g.clip(); g.fillStyle=tex(g,'marble_white',.18);g.fillRect(3,10,58,30); g.restore();
    ell(g,32,24,28,13);g.strokeStyle='#ddbe7a';g.lineWidth=1;g.stroke();
    for (const [x,y] of [[18,22],[43,24]]) {
      fillEll(g,x,y+4,3,1,'#c6d0c8');metalV(g,x-.3,y-1,.6,5);
      fillEll(g,x,y-2,4,2,'rgba(245,231,191,.7)');fillEll(g,x,y-2,2.6,1.2,'#bd7541');
    }
    fillEll(g,32,20,3,2,'#a78e5b'); fillEll(g,32,17,2,2.6,'#fff1cf');
    pool(g,32,17,12,8,LED,.25);
  }
});

def('divider', {
  name: 'Nocturne brass slat planter', cat: 'Plants', size: [152, 100], anchor: [76, 96],
  body: [-70, -12, 140, 12],
  draw(g) {
    shade(g,76,95,74,4,.4);
    for (let x=9; x<149; x+=9) {
      metalV(g,x,9,2.3,78,BRASS);
      g.fillStyle='#473c28';g.fillRect(x+2.3,10,1.2,75);
    }
    fillRR(g,5,76,142,19,3,lin(g,0,76,0,95,[[0,'#374047'],[.2,'#1e262b'],[1,'#10171c']]));
    fillEll(g,76,77,68,5,'#131c19');
    const r=rng(818);
    for(let i=0;i<130;i++) {
      const x=12+r()*127, y=63+r()*15;
      g.strokeStyle=['#2f5740','#40684e','#577452','#203e32'][i%4];g.lineWidth=.8;
      g.beginPath();g.moveTo(x,78);g.quadraticCurveTo(x-5,y,x+(r()-.5)*14,y-7-r()*12);g.stroke();
    }
    ledLine(g,9,94,143,94,.6,LED,4);
  }
});

def('obelisk', {
  name: 'Nocturne orbital brass sculpture', cat: 'Statues & fountains', size: [92, 134], anchor: [46, 128],
  body: [-22, -17, 44, 17],
  draw(g) {
    shade(g,46,128,35,5,.6);
    fillRR(g,23,99,46,28,3,tex(g,'marble_black',.17));
    metalH(g,23,98,46,2,BRASS);ledLine(g,25,125,67,125,.8,LED,4);
    metalV(g,43,35,6,65,BRASS);
    g.save();g.translate(46,52);g.rotate(-.42);
    for(const [rx,ry] of [[30,41],[14,40]]) {
      ell(g,0,0,rx,ry);g.lineWidth=4;g.strokeStyle=lin(g,-30,-40,30,40,BRASS);g.stroke();
      ell(g,0,0,rx-.8,ry-.8);g.lineWidth=.65;g.strokeStyle='#f1dfb2';g.stroke();
    }
    g.restore();fillEll(g,46,52,8,8,lin(g,38,44,54,60,BRASS));pool(g,46,51,13,12,LED,.16);
    label(g,'N',46,113,11,'#d9bf86',{font:FONT.deco});
  }
});

def('medallion', {
  name: 'Nocturne compass marble inlay', cat: 'Rugs', mount: 'flat', size: [184, 132], anchor: [92, 66], body: null,
  draw(g) {
    g.save();ell(g,92,66,89,62);g.clip();g.fillStyle=tex(g,'marble_black',.3);g.fillRect(0,0,184,132);g.restore();
    for (const r of [1,.94,.88]) { ell(g,92,66,89*r,62*r);g.strokeStyle='#bfa16b';g.lineWidth=r===1?2:.6;g.stroke(); }
    g.save();g.translate(92,66);g.scale(1,.69);
    for(let i=0;i<16;i++) {
      const a=i*Math.PI/8, l=i%4===0?65:i%2===0?46:30;
      g.beginPath();g.moveTo(Math.cos(a)*l,Math.sin(a)*l);g.lineTo(Math.cos(a+.6)*9,Math.sin(a+.6)*9);
      g.lineTo(Math.cos(a-.6)*9,Math.sin(a-.6)*9);g.closePath();g.fillStyle=i%2?'#766a50':'#ccb585';g.fill();
    }
    fillEll(g,0,0,13,13,'#152025');label(g,'N',0,1,13,'#e2c991',{font:FONT.deco});g.restore();
  }
});

def('slot_crown', {
  name: 'Nocturne illuminated slot island crown', cat: 'Decor', size: [212, 38], anchor: [106, 34],
  body: [-92,-6,184,6],
  draw(g) {
    fillRR(g,5,6,202,26,6,lin(g,0,6,0,32,[[0,'#4c4840'],[.15,'#172226'],[1,'#0c1217']]));
    ledLine(g,12,7,200,7,.7,LED,5);ledLine(g,12,30,200,30,.6,'#72a9a3',3);
    label(g,'N O C T U R N E   /   S L O T S',106,19,7,'#e7d8b5',{font:FONT.sans});
    for(const x of [12,200]) {fillEll(g,x,18,2,2,'#d7bc83');}
  }
});
