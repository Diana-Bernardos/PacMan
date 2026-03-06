import pygame, sys, math, random
from collections import deque

# optional numpy import; game still works without sound if it's missing
try:
    import numpy as np
except ImportError:
    np = None

# initialize audio before the rest of pygame (stereo output)
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

# sound helper -------------------------------------------------------------

def _make_tone_with_numpy(freq, duration=0.1, volume=0.5):
    """Sine wave via numpy, returned as pygame Sound (stereo)."""
    sr = 44100
    t = np.linspace(0, duration, int(sr * duration), False)
    wave = np.sin(freq * 2 * math.pi * t)
    mono = (wave * 32767).astype(np.int16)
    # duplicate channels for stereo
    arr = np.column_stack((mono, mono))
    snd = pygame.sndarray.make_sound(arr)
    snd.set_volume(volume)
    return snd


def _make_tone_no_numpy(freq, duration=0.1, volume=0.5):
    """Pure-Python sine wave generation (fallback, stereo)."""
    sr = 44100
    count = int(sr * duration)
    # two bytes per sample per channel, two channels
    buf = bytearray(count * 4)
    for i in range(count):
        t = i / sr
        v = math.sin(freq * 2 * math.pi * t) * volume
        sample = int(v * 32767)
        # write same sample to left and right (little endian)
        buf[4*i:4*i+2] = sample.to_bytes(2, 'little', signed=True)
        buf[4*i+2:4*i+4] = sample.to_bytes(2, 'little', signed=True)
    return pygame.mixer.Sound(buffer=buf)

# choose appropriate maker based on numpy availability
_maker = _make_tone_with_numpy if np is not None else _make_tone_no_numpy

# pre-generate commonly used effects
try:
    SND_DOT       = _maker(880, 0.04, 0.2)
    SND_PELLET    = _maker(440, 0.10, 0.3)
    SND_EATGHOST  = _maker(1200, 0.15, 0.5)
    SND_DIE       = _maker(200,  0.50, 0.5)
except Exception as e:
    # sound generation failed, continue without audio but notify user
    print("[PAC-MAN] warning: audio disabled (", e, ")")
    SND_DOT = SND_PELLET = SND_EATGHOST = SND_DIE = None

# ── Constantes ────────────────────────────────────────────────────────────────
TILE, COLS, ROWS = 24, 21, 23
HUD = 60
W, H = COLS * TILE, ROWS * TILE + HUD
FPS  = 60

BLACK  = (0,0,0);      DARK   = (8,8,24)
WBLUE  = (30,90,200);  WGLOW  = (60,140,255)
DOTC   = (255,220,150);PELC   = (255,180,50)
YELL   = (255,220,0);  WHITE  = (255,255,255)
GREEN  = (100,255,100);RED    = (255,80,80)
SCARED = (40,40,200);  SCFLASH= (200,200,255)
GCOLS  = [(255,0,0),(255,184,255),(0,255,220),(255,184,82)]

MAZE = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,2,2,2,2,2,2,2,2,2,1,2,2,2,2,2,2,2,2,2,1],
    [1,3,1,1,2,1,1,1,2,1,1,1,2,1,1,1,2,1,1,3,1],
    [1,2,1,1,2,1,1,1,2,1,1,1,2,1,1,1,2,1,1,2,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,2,1,2,1,1,1,1,1,1,1,2,1,2,1,1,2,1],
    [1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1],
    [1,1,1,1,2,1,1,1,0,0,0,0,0,1,1,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,0,0,0,0,0,0,0,0,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,1,1,4,4,4,1,1,0,1,2,1,1,1,1],
    [0,0,0,0,2,0,0,1,0,0,0,0,0,1,0,0,2,0,0,0,0],
    [1,1,1,1,2,1,0,1,1,1,1,1,1,1,0,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,0,0,0,0,0,0,0,0,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,1,1,1,1,1,1,1,0,1,2,1,1,1,1],
    [1,2,2,2,2,2,2,2,2,2,1,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,2,1,1,1,2,1,1,1,2,1,1,1,2,1,1,2,1],
    [1,3,2,1,2,2,2,2,2,2,0,2,2,2,2,2,2,1,2,3,1],
    [1,1,2,1,2,1,2,1,1,1,1,1,1,1,2,1,2,1,2,1,1],
    [1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1],
    [1,2,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,1,1,2,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,2,1,1,1,2,1,1,1,2,1,1,1,2,1,1,2,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]

UP,DOWN,LEFT,RIGHT = (0,-1),(0,1),(-1,0),(1,0)
DIRS = [UP,DOWN,LEFT,RIGHT]

def tile_free(maze, col, row, allow_door=False):
    if col < 0: col = COLS-1
    if col >= COLS: col = 0
    if not (0 <= row < ROWS): return False
    c = maze[row][col]
    return c != 1 and (c != 4 or allow_door)

def bfs(maze, sc, sr, tc, tr, allow_door=False):
    visited = {(sr,sc)}
    q = deque([(sr,sc,[])])
    while q:
        r,c,path = q.popleft()
        if r==tr and c==tc: return path
        for d in DIRS:
            nr,nc = r+d[1], c+d[0]
            if nc<0: nc=COLS-1
            if nc>=COLS: nc=0
            if 0<=nr<ROWS and (nr,nc) not in visited and tile_free(maze,nc,nr,allow_door):
                visited.add((nr,nc)); q.append((nr,nc,path+[d]))
    return []

class Pac:
    SPEED = 2.2
    def __init__(self):  self.reset()
    def reset(self):
        self.x,self.y = 10*TILE+TILE//2, 17*TILE+TILE//2+HUD
        self.dir = (0,0); self.want = (0,0)
        self.mouth = 0.0; self.mdir = 1; self.alive = True; self.dframe = 0

    def col(self): return int(self.x) // TILE
    def row(self): return int(self.y - HUD) // TILE
    def center(self):
        # compute the exact pixel coordinates of the tile center that contains
        # the sprite. need to subtract HUD before flooring and then add it back.
        bx = int(self.x) - (int(self.x) % TILE) + TILE//2
        by_nohud = int(self.y) - HUD
        by = by_nohud - (by_nohud % TILE) + TILE//2 + HUD
        return (bx, by)

    def at_center(self):
        # allow a small tolerance for floating movement
        cx, cy = self.center()
        return abs(self.x - cx) <= 3 and abs(self.y - cy) <= 3

    def update(self, maze):
        if not self.alive:
            self.dframe += 1; return
        # Only move if a direction has been chosen
        if self.want != (0,0):
            if self.at_center() and tile_free(maze, self.col()+self.want[0], self.row()+self.want[1]):
                self.dir = self.want
        if self.dir == (0,0):
            return
        nx = self.x + self.dir[0]*self.SPEED
        ny = self.y + self.dir[1]*self.SPEED
        if nx<0: nx+=W
        if nx>=W: nx-=W
        if tile_free(maze, self.col()+self.dir[0], self.row()+self.dir[1]):
            self.x,self.y = nx,ny
        else:
            cx,cy = self.center(); self.x,self.y = cx,cy
        self.mouth += 0.18*self.mdir
        if self.mouth>=1: self.mdir=-1
        if self.mouth<=0: self.mdir=1

    def draw(self, surf):
        r = TILE//2-1
        px, py = int(self.x), int(self.y)
        if not self.alive:
            f = min(self.dframe,40)
            pygame.draw.circle(surf,(max(0,255-f*6),max(0,220-f*6),0),(px,py),max(1,r-f//2))
            return
        ang = {RIGHT:0,DOWN:270,LEFT:180,UP:90}.get(self.dir, 0)
        mo  = int(38*self.mouth) if self.dir != (0,0) else 10
        pts = [(px,py)]
        start = math.radians(ang+mo); end = math.radians(ang+360-mo)
        for i in range(37):
            a = start+(end-start)*i/36
            pts.append((px+r*math.cos(a), py-r*math.sin(a)))
        pygame.draw.polygon(surf, YELL, pts)
        ex = {RIGHT:(-2,-r//2),LEFT:(2,-r//2),UP:(-r//2,2),DOWN:(r//2,-2)}.get(self.dir,(0,-r//2))
        pygame.draw.circle(surf, BLACK, (px+ex[0], py+ex[1]), 2)

class Ghost:
    def __init__(self, idx, maze):
        self.idx=idx; self.color=GCOLS[idx]; self.maze=maze
        self.homes=[(10,10),(10,10),(10,10),(10,10)]
        self.reset()

    def reset(self):
        hx,hy = self.homes[self.idx]
        self.x,self.y = hx*TILE+TILE//2, hy*TILE+TILE//2+HUD
        self.dir=UP; self.scared=False; self.scared_t=0
        self.returning=False; self.release_t=self.idx*FPS*3; self.released=False

    def col(self): return int(self.x)//TILE
    def row(self): return int(self.y-HUD)//TILE
    def center(self):
        bx = int(self.x) - (int(self.x) % TILE) + TILE//2
        by_nohud = int(self.y) - HUD
        by = by_nohud - (by_nohud % TILE) + TILE//2 + HUD
        return (bx, by)

    def at_center(self):
        cx, cy = self.center()
        return abs(self.x - cx) <= 2 and abs(self.y - cy) <= 2

    def frighten(self):
        if self.returning: return
        self.scared=True; self.scared_t=FPS*8
        rev=(-self.dir[0],-self.dir[1])
        if rev in DIRS: self.dir=rev

    def eaten(self): self.scared=False; self.returning=True

    def choose_dir(self, pac):
        if self.returning:
            hx,hy=self.homes[self.idx]
            if self.col()==hx and self.row()==hy:
                self.returning=False; self.released=True; return
            path=bfs(self.maze,self.col(),self.row(),hx,hy,allow_door=True)
            if path: self.dir=path[0]; return
        
        in_house = 8 <= self.col() <= 12 and 9 <= self.row() <= 10
        opts = [d for d in DIRS if d != (-self.dir[0], -self.dir[1]) and tile_free(self.maze, self.col()+d[0], self.row()+d[1], allow_door=in_house)]
        if not opts: opts = [d for d in DIRS if tile_free(self.maze, self.col()+d[0], self.row()+d[1], allow_door=in_house)]
        
        if self.scared and not in_house:
            if opts: self.dir=random.choice(opts)
            return

        if in_house:
            tx, ty = 10, 8
        else:
            pc, pr = pac.col(), pac.row()
            tx, ty = pc, pr
            if self.idx == 1: tx += pac.dir[0]*4; ty += pac.dir[1]*4
            elif self.idx == 2: tx = COLS-1-pc
            elif self.idx == 3:
                if abs(self.col()-pc) + abs(self.row()-pr) < 8: tx, ty = 1, ROWS-2
            
        if opts:
            best_d = None; best_o = opts[0]
            for o in opts:
                dist = (self.col()+o[0] - tx)**2 + (self.row()+o[1] - ty)**2
                if best_d is None or dist < best_d:
                    best_d = dist; best_o = o
            self.dir = best_o

    def update(self, pac):
        if not self.released:
            self.release_t-=1
            if self.release_t<=0: self.released=True
            return
        speed = 3.5 if self.returning else (1.1 if self.scared else 1.8)
        if self.at_center(): self.choose_dir(pac)
        if self.scared:
            self.scared_t-=1
            if self.scared_t<=0: self.scared=False
        nx=self.x+self.dir[0]*speed; ny=self.y+self.dir[1]*speed
        if nx<0: nx+=W
        if nx>=W: nx-=W
        
        in_house = 8 <= self.col() <= 12 and 9 <= self.row() <= 10
        if tile_free(self.maze,self.col()+self.dir[0],self.row()+self.dir[1],allow_door=self.returning or in_house):
            self.x,self.y=nx,ny
        else:
            cx,cy=self.center(); self.x,self.y=cx,cy

    def draw(self, surf, tick):
        r=TILE//2-1
        gx, gy = int(self.x), int(self.y)
        flash=(self.scared_t<FPS*3 and (tick//6)%2==0)
        color=SCFLASH if flash else (SCARED if self.scared else ((150,150,170) if self.returning else self.color))
        pygame.draw.circle(surf, color, (gx,gy), r)
        pts=[(gx-r,gy+r)]
        for i in range(5):
            bx=gx-r+i*(r*2//4); by=gy+r-(4 if i%2==0 else 0)
            pts.append((bx,by))
        pts.append((gx+r,gy+r))
        pygame.draw.polygon(surf,color,pts)
        ec=(255,255,255) if not self.returning else (0,200,255)
        for ox in (-r//2, r//2):
            pygame.draw.circle(surf,ec,(gx+ox,gy-r//3),r//3)
            pygame.draw.circle(surf,(0,50,150),(gx+ox+self.dir[0]*2,gy-r//3+self.dir[1]*2),r//5)

def draw_maze(surf, maze, tick):
    for row in range(ROWS):
        for col in range(COLS):
            c=maze[row][col]; rx=col*TILE; ry=row*TILE+HUD
            if c==1:
                def is_wall(r,cc,maze=maze):
                    if not(0<=r<ROWS and 0<=cc<COLS): return True
                    return maze[r][cc]==1
                p=3
                pygame.draw.rect(surf,(15,15,40),pygame.Rect(rx,ry,TILE,TILE))
                pygame.draw.rect(surf,WBLUE,pygame.Rect(rx+p,ry+p,TILE-p*2,TILE-p*2),border_radius=3)
                if is_wall(row-1,col): pygame.draw.rect(surf,WBLUE,pygame.Rect(rx+p,ry,TILE-p*2,p+1))
                if is_wall(row+1,col): pygame.draw.rect(surf,WBLUE,pygame.Rect(rx+p,ry+TILE-p-1,TILE-p*2,p+1))
                if is_wall(row,col-1): pygame.draw.rect(surf,WBLUE,pygame.Rect(rx,ry+p,p+1,TILE-p*2))
                if is_wall(row,col+1): pygame.draw.rect(surf,WBLUE,pygame.Rect(rx+TILE-p-1,ry+p,p+1,TILE-p*2))
            elif c==2:
                pygame.draw.circle(surf,DOTC,(rx+TILE//2,ry+TILE//2),2)
            elif c==3:
                pr=5+int(2*math.sin(tick*0.08))
                pygame.draw.circle(surf,PELC,(rx+TILE//2,ry+TILE//2),pr)

def draw_hud(surf, score, hi, level, lives, font_lg, font_sm):
    pygame.draw.rect(surf,(5,5,20),pygame.Rect(0,0,W,HUD))
    pygame.draw.line(surf,WGLOW,(0,HUD-1),(W,HUD-1),1)
    def t(txt,f,col,cx,cy):
        s=f.render(txt,True,col); surf.blit(s,s.get_rect(center=(cx,cy)))
    t("SCORE",font_sm,(150,150,200),55,16);  t(str(score),font_lg,YELL,55,40)
    t("BEST", font_sm,(150,150,200),W//2,16); t(str(max(score,hi)),font_lg,WHITE,W//2,40)
    t("LEVEL",font_sm,(150,150,200),W-55,16); t(str(level),font_lg,GREEN,W-55,40)
    for i in range(lives-1):
        lx=8+i*22; ly=HUD-12; r=8
        pts=[(lx,ly)]
        for s in range(37):
            a=math.radians(25+s*(310/36)); pts.append((lx+r*math.cos(a),ly-r*math.sin(a)))
        pygame.draw.polygon(surf,YELL,pts)

class Game:
    def __init__(self):
        self.screen=pygame.display.set_mode((W,H))
        pygame.display.set_caption("PAC-MAN · Python")
        self.clock=pygame.time.Clock()
        self.font_lg=pygame.font.SysFont("courier",26,bold=True)
        self.font_md=pygame.font.SysFont("courier",20,bold=True)
        self.font_sm=pygame.font.SysFont("courier",13)
        self.hi=0; self.tick=0; self.state="menu"; self._load()

    def _load(self):
        self.maze=[r[:] for r in MAZE]
        self.pac=Pac()
        self.ghosts=[Ghost(i,self.maze) for i in range(4)]
        self.score=0; self.lives=3; self.level=1; self.freeze=0; self.combo=0
        self.dots=sum(c in(2,3) for row in self.maze for c in row)
        # play a quick sound to indicate game start/reload
        if SND_DOT: SND_DOT.play()

    def _txt(self,t,f,col,cx,cy):
        s=f.render(t,True,col); self.screen.blit(s,s.get_rect(center=(cx,cy)))

    def _render(self):
        self.screen.fill(DARK)
        draw_maze(self.screen,self.maze,self.tick)
        for g in self.ghosts: g.draw(self.screen,self.tick)
        self.pac.draw(self.screen)
        draw_hud(self.screen,self.score,self.hi,self.level,self.lives,self.font_lg,self.font_sm)

    def _menu(self):
        self.screen.fill(DARK)
        t=self.tick*0.04
        random.seed(42)
        for i in range(50):
            br=int(100+80*math.sin(self.tick*0.03+i))
            pygame.draw.circle(self.screen,(br//5,br//5,br//2),(random.randint(0,W),random.randint(0,H)),1)
        cy=H//2-110+int(6*math.sin(t))
        for ox,oy in [(-2,0),(2,0),(0,-2),(0,2)]:
            s=self.font_lg.render("PAC-MAN",True,(120,80,0)); self.screen.blit(s,s.get_rect(center=(W//2+ox,cy+oy)))
        self._txt("PAC-MAN",self.font_lg,YELL,W//2,cy)
        self._txt("PYTHON EDITION",self.font_sm,(180,180,220),W//2,cy+36)
        px=W//2+int(70*math.cos(t*0.8)); py=H//2-10
        mo=int(35*abs(math.sin(t*3)))
        pts=[(px,py)]
        for i in range(37):
            a=math.radians(mo+i*((360-mo*2)/36)); pts.append((px+22*math.cos(a),py-22*math.sin(a)))
        pygame.draw.polygon(self.screen,YELL,pts)
        for i,gc in enumerate(GCOLS):
            gx=W//2-50+i*36+int(12*math.sin(t+i)); gy=H//2+50
            pygame.draw.circle(self.screen,gc,(gx,gy),13)
        if (self.tick//25)%2==0:
            self._txt("SPACE / ENTER  TO  START",self.font_sm,WHITE,W//2,H//2+110)
        self._txt("WASD / ARROWS  ·  P=PAUSE  ·  ESC=QUIT",self.font_sm,(120,120,160),W//2,H//2+148)
        if self.hi>0: self._txt(f"BEST  {self.hi}",self.font_sm,(255,200,50),W//2,H//2+180)

    def _overlay(self,title,col,sub):
        ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,170)); self.screen.blit(ov,(0,0))
        p=int(220+35*math.sin(self.tick*0.08))
        c=(p,40,40) if col=="red" else (40,p,40) if col=="green" else YELL
        self._txt(title,self.font_lg,c,W//2,H//2-40)
        self._txt(f"SCORE  {self.score}",self.font_md,YELL,W//2,H//2+5)
        if (self.tick//25)%2==0: self._txt(sub,self.font_sm,WHITE,W//2,H//2+45)

    def _check_dots(self):
        col,row=self.pac.col(),self.pac.row()
        if 0<=row<ROWS and 0<=col<COLS:
            c=self.maze[row][col]
            if c==2:
                self.maze[row][col]=0; self.score+=10; self.dots-=1
                if SND_DOT: SND_DOT.play()
            elif c==3:
                self.maze[row][col]=0; self.score+=50; self.dots-=1; self.combo=0
                if SND_PELLET: SND_PELLET.play()
                for g in self.ghosts: g.frighten()

    def _check_ghosts(self):
        for g in self.ghosts:
            if g.returning: continue
            if abs(g.x-self.pac.x)+abs(g.y-self.pac.y)<TILE-4:
                if g.scared:
                    g.eaten(); self.combo+=1
                    self.score+=200*(2**min(self.combo-1,4))
                    if SND_EATGHOST: SND_EATGHOST.play()
                elif self.state=="play":
                    self.pac.alive=False; self.state="dying"; self.freeze=75
                    if SND_DIE: SND_DIE.play()

    def run(self):
        while True:
            self.tick+=1; self.clock.tick(FPS)
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
                if ev.type==pygame.KEYDOWN: self._key(ev.key)
            # in play state also poll current key state to handle arrow
            # presses that might be missed or held down
            if self.state=="play":
                keys=pygame.key.get_pressed()
                if keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_KP8]:
                    self.pac.want=UP
                elif keys[pygame.K_DOWN] or keys[pygame.K_s] or keys[pygame.K_KP2]:
                    self.pac.want=DOWN
                elif keys[pygame.K_LEFT] or keys[pygame.K_a] or keys[pygame.K_KP4]:
                    self.pac.want=LEFT
                elif keys[pygame.K_RIGHT] or keys[pygame.K_d] or keys[pygame.K_KP6]:
                    self.pac.want=RIGHT
            if self.state=="menu":
                self._menu()
            elif self.state=="play":
                if self.freeze>0: self.freeze-=1
                else:
                    self.pac.update(self.maze)
                    for g in self.ghosts: g.update(self.pac)
                    self._check_dots(); self._check_ghosts()
                    if self.dots<=0:
                        self.hi=max(self.hi,self.score); self.state="win"; self.freeze=120
                self._render()
            elif self.state=="dying":
                self.freeze-=1; self._render()
                if self.freeze<=0:
                    self.lives-=1
                    if self.lives<=0: self.hi=max(self.hi,self.score); self.state="gameover"
                    else: self.pac.reset(); [g.reset() for g in self.ghosts]; self.state="play"; self.freeze=60
            elif self.state=="paused":
                self._render(); self._overlay("PAUSED","yellow","P  TO  CONTINUE")
            elif self.state=="gameover":
                self._render(); self._overlay("GAME  OVER","red","SPACE  TO  MENU")
            elif self.state=="win":
                self.freeze-=1; self._render(); self._overlay("YOU  WIN !","green","SPACE  FOR  NEXT  LEVEL")
            pygame.display.flip()

    def _key(self,key):
        # dictionary maps key constants to direction vectors
        dm={
            pygame.K_UP:UP, pygame.K_DOWN:DOWN, pygame.K_LEFT:LEFT, pygame.K_RIGHT:RIGHT,
            pygame.K_w:UP, pygame.K_s:DOWN, pygame.K_a:LEFT, pygame.K_d:RIGHT,
            # numeric keypad arrows (some keyboards send these instead)
            pygame.K_KP8:UP, pygame.K_KP2:DOWN, pygame.K_KP4:LEFT, pygame.K_KP6:RIGHT
        }
        # directional input: either move if playing or start the game
        if key in dm:
            if self.state=="play":
                self.pac.want=dm[key]
                return
            elif self.state=="menu":
                # begin playing immediately and honor the direction
                self._load(); self.state="play"
                self.freeze=0          # skip intro delay when user is already giving a direction
                self.pac.want=dm[key]
                return
        if key==pygame.K_ESCAPE:
            pygame.quit(); sys.exit()
        if key==pygame.K_p:
            if self.state=="play": self.state="paused"
            elif self.state=="paused": self.state="play"
        if key in(pygame.K_SPACE,pygame.K_RETURN):
            if self.state=="menu": self._load(); self.state="play"; self.freeze=60
            elif self.state=="gameover": self._load(); self.state="menu"
            elif self.state=="win":
                self.level+=1; self.maze=[r[:] for r in MAZE]
                self.dots=sum(c in(2,3) for row in self.maze for c in row)
                self.pac.reset(); self.ghosts=[Ghost(i,self.maze) for i in range(4)]
                Pac.SPEED=min(3.2,2.2+(self.level-1)*0.1)
                self.state="play"; self.freeze=60

if __name__=="__main__":
    Game().run()