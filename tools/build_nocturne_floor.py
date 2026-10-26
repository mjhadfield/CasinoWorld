#!/usr/bin/env python3
"""Build Casino Floor — Nocturne as an unplaced library blueprint.

Run with server/.venv/bin/python tools/build_nocturne_floor.py to prepare art and
validate the room in .dev/nocturne. Add --install to merge its art into the live
library and save the room through the revision-checked draft API. Never publishes
or places a room. Rebuilding preserves the new room's item ids and table styles.
"""
import argparse
import asyncio
import copy
import json
from pathlib import Path

import numpy as np
from PIL import Image

import build_vegas_floor as vegas

ROOT = vegas.ROOT
HERE = ROOT / 'tools' / 'nocturne_floor'
OUT = ROOT / '.dev' / 'nocturne'
ROOM_ID = 'nocturne_floor'
CREDIT = 'Original Nocturne furniture; ambientCG CC0 materials (tools/vegas_floor/textures/CREDITS.md)'


async def render():
    from playwright.async_api import async_playwright
    textures = {p.stem: vegas.data_url(p, 'image/jpeg') for p in vegas.TEXTURES.glob('*.jpg')}
    fonts = {family: vegas.data_url(vegas.FONTS / filename, 'font/ttf') for family, filename in
             [('Montserrat', 'Montserrat-SemiBold.ttf'), ('Josefin Sans', 'JosefinSans-SemiBold.ttf'), ('Cinzel', 'Cinzel-SemiBold.ttf')]}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.set_content('<!doctype html><script>' + (vegas.HERE / 'pieces.js').read_text()
                               + '\n' + (HERE / 'pieces.js').read_text() + '</script>')
        result = await page.evaluate('([t,f]) => renderAll(t,f)', [textures, fonts])
        await browser.close()
        return result


def carpet(size=512):
    """Quiet, seamless, woven teal contour pattern, 256 game pixels per repeat."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    t = 2 * np.pi
    field = y * 4 + .26 * np.sin(t*x) + .1 * np.sin(t*(2*x+y))
    d = np.abs((field + .5) % 1 - .5)
    img = np.broadcast_to(vegas._hex('#14292e'), (size,size,3)).copy()
    img = vegas._layer(img, np.clip((.09-d)/.04,0,1)*.55, '#254448')
    img = vegas._layer(img, np.clip((.009-d)/.005,0,1)*.6, '#9c8459')
    # Subtle cross-weave and real pile; no random noise at the tile boundary.
    img *= vegas._fibre(size)[...,None]
    return Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8))


def blueprint(source, looks):
    items = []

    def put(a,x,y,facing='down',group=None,**props):
        it = {'asset':'a:'+a,'x':x,'y':y,'facing':facing,'props':props}
        if group: it['group']=group
        items.append(it)

    def figure(key,x,y,facing='down'):
        items.append({'asset':'npc','x':x,'y':y,'facing':facing,'props':{'look':looks[key],'name':''}})

    # Draw flat layers first. The promenade remains free all the way to the steps.
    put('vegas_stage',704,428,group='nocturne_salon')
    put('nocturne_medallion',704,824)
    for x,y in [(328,612),(1080,612),(222,280),(1186,320),(320,902),(1088,902)]:
        put('vegas_glow_warm',x,y)

    # One master table, preserving the original's limits, swap animation and pace.
    master = copy.deepcopy(next(i for i in source['items'] if i['asset']=='table:master_table'))
    for k in ['id','group']: master.pop(k,None)
    master.update(x=704,y=302,rot=0,group='nocturne_salon')
    master['props']['label']='Master Table'
    items.append(master)
    for x in [560,848]:
        put('nocturne_rail_front',x,430,group='nocturne_salon')
    for x in [466,942]:
        put('nocturne_rail_side',x,424,group='nocturne_salon')
    for x in [494,914]: put('vegas_planter_palm',x,154,group='nocturne_salon')
    put('nocturne_signature',704,62)
    # Live progressive display, set apart from the signature so both are legible.
    put('modern_jackpot_screen',1192,44)
    for x in [440,968]: put('vegas_led_column',x,460)
    figure('host',792,476,'left')

    for asset,x in [('roulette',328),('craps',1080)]:
        props=copy.deepcopy(next(i['props'] for i in source['items'] if i['asset']=='table:'+asset))
        props.update(label=asset.title(),sign='left' if asset=='roulette' else 'right')
        items.append({'asset':'table:'+asset,'x':x,'y':658,'rot':0,'props':props})

    # Cocktail bar and a furnished lounge, with small tabletop drinks and candles.
    put('vegas_back_bar',224,66)
    put('vegas_bar_counter',224,192)
    figure('bartender_f',174,148);figure('bartender_m',280,148)
    for x in [114,158,202,246,290,334]: put('vegas_bar_stool',x,218)
    put('nocturne_banquette',154,308)
    put('nocturne_cocktail',154,350)
    put('vegas_armchair',95,385,'right');put('vegas_armchair',214,385,'left')
    put('vegas_high_top',342,332)
    put('vegas_bar_stool',316,352);put('vegas_bar_stool',370,352)
    put('nocturne_divider',222,450)
    put('vegas_planter_palm',46,448)
    figure('waitress',306,408,'left')

    # Cashier and ATM are approached from the front; the seating is to their south.
    put('vegas_cashier_cage',1190,188)
    figure('cashier_f',1103,158);figure('cashier_m',1277,158)
    put('vegas_atm',1014,188)
    put('nocturne_banquette',1190,302)
    put('nocturne_cocktail',1190,348)
    put('vegas_armchair',1128,390,'right');put('vegas_armchair',1252,390,'left')
    put('nocturne_divider',1190,450)
    put('vegas_planter_palm',1360,448)

    # Exactly two six-cabinet banks, with a separate illuminated header behind each.
    variants = next(i['props']['slots'] for i in source['items'] if i['asset']=='bank:6')
    for x in [320,1088]:
        items.append({'asset':'bank:6','x':x,'y':916,'facing':'down','props':{'slots':variants[:]}})
        put('nocturne_slot_crown',x,822)
        put('vegas_pylon_slots',x+166 if x<704 else x-166,930)
    # Sculpture on its own island, clear of the promenade, with a view across the pits.
    put('nocturne_obelisk',550,812)
    for x in [594,814]: put('vegas_led_column',x,1064)
    for x in [54,1354]: put('vegas_planter_palm',x,1056)
    for x in [50,422,986,1360]: put('vegas_wall_sconce',x,60)

    def patch(x,y,w,h,texture,shape='rect',radius=0,border='inlay',width=3):
        return dict(x=x,y=y,w=w,h=h,texture=texture,tint='#ffffff',shape=shape,radius=radius,
                    border={'style':border,'width':width,'colour':'#bfa16b'})
    patches=[
        patch(8,72,416,396,'vegas_walnut','rounded',18),
        patch(984,72,416,396,'vegas_walnut','rounded',18),
        patch(80,490,488,268,'vegas_marble_black','rounded',30,'double',5),
        patch(840,490,488,268,'vegas_marble_black','rounded',30,'double',5),
        patch(96,508,456,232,'nocturne_carpet','rounded',22,'line',1),
        patch(856,508,456,232,'nocturne_carpet','rounded',22,'line',1),
        patch(96,810,448,208,'vegas_marble_black','rounded',36,'double',5),
        patch(864,810,448,208,'vegas_marble_black','rounded',36,'double',5),
        patch(112,826,416,176,'nocturne_carpet','rounded',26,'line',1),
        patch(880,826,416,176,'nocturne_carpet','rounded',26,'line',1),
        patch(632,464,144,616,'vegas_marble_white'),
        patch(400,468,608,44,'vegas_marble_white'),
        patch(40,768,1328,40,'vegas_marble_white'),
    ]
    points=[dict(name='entrance',x=704,y=1036,kind='spawn',weight=1,linger=0),
            dict(name='staff_arrival',x=1362,y=1024,kind='arrival',weight=1,linger=0)]
    for name,x,y,weight,linger in [('cocktails',266,372,3,35),('cashier',1190,232,1,12),
            ('lounge',1190,414,2,30),('salon',704,404,2,12),('gallery',704,564,1,8),
            ('roulette',340,722,2,10),('craps',1090,728,2,10),('slots_west',320,1018,1,12),
            ('slots_east',1088,1018,1,12),('cross_aisle',704,788,1,6)]:
        points.append(dict(name=name,x=x,y=y,kind='wander',weight=weight,linger=linger))
    zones=[dict(x=80,y=72,w=288,h=62,kind='block'),dict(x=1060,y=72,w=264,h=62,kind='block'),
           # Keep NPCs out of the tight service pocket behind Roulette's tall results
           # board, as in the source blueprint. Joining it to the table footprint also
           # avoids near-tangent holes in Godot's wider navigation bake.
           dict(x=104,y=514,w=56,h=176,kind='npc_block')]
    # 1440 wide puts the central axis at 720: x=-416 then meets the Modern lobby's
    # x=304 door exactly, while both room dimensions and position follow its 32px grid.
    for thing in items+points+zones: thing['x']+=16
    for p in patches:
        if p['x']==8: p['w']+=16
        else:
            p['x']+=16
            if p['x']+p['w']==1416: p['w']+=16
    return dict(id=ROOM_ID,name='Casino Floor — Nocturne',map_name='Nocturne',placed=False,
                x=-416,y=-1152,w=1440,h=1088,floor={'texture':'nocturne_carpet','tint':'#ffffff'},
                walls={'style':'onyx','sign':'','sign_at':720},doors=[],items=items,patches=patches,
                paths={'points':points,'zones':zones})


def validate(room, data_dir, generated):
    from casino_server import plan, plan_assets
    plan_assets.AssetLibrary(data_dir)
    for aid,a in generated['assets'].items(): plan.ASSETS[aid]=a
    for fid,f in generated['floors'].items(): plan.FLOORS[fid]=f
    empty={'rooms':[],'next':{},'rev':0,'spawn':''}
    scratch=plan.clean({'rooms':[room],'spawn':ROOM_ID+'/entrance'},empty)
    # Validate a placed COPY to exercise player AND NPC reachability as well as overlaps.
    scratch['rooms'][0]['placed']=True
    issues=plan.problems(scratch, ROOT/'server'/'slot_builds')
    if issues: raise RuntimeError('\n'.join(p['message'] for p in issues))
    print('Layout: no overlaps, off-floor objects, or unreachable player/NPC destinations.')


def install(server,data_dir,room,generated):
    call=lambda method,path,body=None: vegas._call(server,method,path,body)
    # Read the server before touching the library; never rely on a stale local draft.
    view=call('GET','/api/plan')
    old=next((r for r in view['draft']['rooms'] if r['id']==ROOM_ID),None)
    if old and old['placed']: raise RuntimeError('Nocturne is already placed; refusing to alter a placed room.')
    if old:
        # Match by asset and position, so rebuilding decorative runs never reassigns table ids.
        previous={(i['asset'],i['x'],i['y']):i for i in old['items']}
        remaining=old['items'][:]
        for it in room['items']:
            was=previous.get((it['asset'],it['x'],it['y']))
            if was not in remaining: was=None
            if was is None: was=next((i for i in remaining if i['asset']==it['asset']),None)
            if was:
                it['id']=was['id']
                remaining.remove(was)
    lib=data_dir/'plan_assets'
    uploads=json.loads((lib/'uploads.json').read_text())
    for section in ['assets','floors']:
        uploads[section].update(generated[section])
    for file in OUT.glob('*.png'):
        if file.name.startswith(('nocturne_','floor_nocturne_')): (lib/file.name).write_bytes(file.read_bytes())
    tmp=lib/'nocturne-uploads.tmp';tmp.write_text(json.dumps(uploads,indent=1));tmp.replace(lib/'uploads.json')
    # The normal asset update reloads the complete library and broadcasts plan_art_changed.
    call('PATCH','/api/plan-assets/nocturne_signature',{'name':generated['assets']['nocturne_signature']['name']})
    draft=view['draft']
    saved=call('PUT','/api/plan/draft',dict(rooms=[r for r in draft['rooms'] if r['id']!=ROOM_ID]+[room],
                                        spawn=draft['spawn'],base_rev=draft['rev']))
    new=next(r for r in saved['draft']['rooms'] if r['id']==ROOM_ID)
    for it in new['items']:
        if not it['asset'].startswith('table:'): continue
        kind=vegas.KIND_OF[it['asset']]
        have=call('GET','/api/table-styles?kind='+kind)
        if it['id'] in have['tables']: continue
        if kind=='cards': sid='dark_modern'
        else:
            sid='nocturne'
            style=copy.deepcopy(vegas.STYLES[kind]);style['name']='Nocturne'
            style['design']['felt']['colour']='#20393d'
            style['design']['rail']['bead']='brass'
            if kind=='roulette': style['design']['chairs']['frame']='brass'
            if sid not in have['styles']: call('PUT',f'/api/table-styles/styles/{sid}?kind={kind}',style)
        call('PUT',f'/api/table-styles/tables?kind={kind}',{'tables':{it['id']:sid}})
    assert new['placed'] is False
    assert [r for r in saved['draft']['rooms'] if r['id']!=ROOM_ID]==[r for r in draft['rooms'] if r['id']!=ROOM_ID]
    assert not [p for p in saved['problems'] if p['room']==ROOM_ID]
    assert saved['draft']['spawn']==draft['spawn']
    (OUT/'saved-room.json').write_text(json.dumps(new,indent=2))
    print('Saved in library:',new['name'],'— revision',saved['draft']['rev'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,default=ROOT/'server'/'data')
    ap.add_argument('--server',default='http://127.0.0.1:8660')
    ap.add_argument('--install',action='store_true')
    args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    generated={'assets':{},'floors':{}}
    for key,piece in asyncio.run(render()).items():
        aid='nocturne_'+key;files={}
        for i,(f,url) in enumerate(piece['pictures'].items()):
            filename=aid+('' if i==0 else '_'+f)+'.png'
            vegas.png(url).save(OUT/filename);files[f]=filename
        generated['assets'][aid]=vegas.entry(piece,files)
        generated['assets'][aid]['credit']=CREDIT
    carpet().save(OUT/'floor_nocturne_carpet.png')
    generated['floors']['nocturne_carpet']=dict(name='Nocturne woven teal',file='floor_nocturne_carpet.png',scale=2,credit=CREDIT)
    source=json.loads((args.data/'plan'/'draft.json').read_text())
    original=next(r for r in source['rooms'] if r['name']=='Casino Floor')
    # Reuse already built house staff looks; no character builds or live roster changes.
    prior=next(r for r in source['rooms'] if r['id']=='vegas_floor')
    figures=[i['props']['look'] for i in prior['items'] if i['asset']=='npc']
    looks=dict(zip(['host','bartender_f','bartender_m','waitress','cashier_f','cashier_m'],figures))
    room=blueprint(original,looks)
    validate(room,args.data,generated)
    (OUT/'room.json').write_text(json.dumps(room,indent=2))
    (OUT/'assets.json').write_text(json.dumps(generated,indent=2))
    if args.install: install(args.server,args.data,room,generated)
    else: print('Prepared in',OUT,'(use --install to save to the library)')


if __name__=='__main__': main()
