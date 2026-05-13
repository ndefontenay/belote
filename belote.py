#!/usr/bin/env python3
"""
Belote – French trick-taking card game
Rules: Fédération Française de Belote (see RULES.md)
Teams: South+North vs East+West  |  1 human (South) + 3 AI
"""
import tkinter as tk
import random
from typing import List, Tuple, Optional

# ── Constants ──────────────────────────────────────────────────────────────────
SUITS      = ['♠', '♥', '♦', '♣']
SUIT_RED   = {'♠': False, '♥': True, '♦': True, '♣': False}
RANKS      = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']

TRUMP_ORDER = ['J', '9', 'A', '10', 'K', 'Q', '8', '7']
PLAIN_ORDER = ['A', '10', 'K', 'Q', 'J', '9', '8', '7']

TRUMP_PTS = {'J': 20, '9': 14, 'A': 11, '10': 10, 'K': 4, 'Q': 3, '8': 0, '7': 0}
PLAIN_PTS = {'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0, '8': 0, '7': 0}

WIN_TARGET = 501
SCORE_W    = 215   # width of the right-side score/history panel

PLAYER_NAMES = ['You', 'East', 'North', 'West']

# Card dimensions (fixed regardless of window size)
CW, CH = 68, 96

# Default window size
DEFAULT_W, DEFAULT_H = 1060, 740

BG      = '#2d6a4f'
BG_DARK = '#1b4332'
C_WHITE = '#fefae0'
C_BACK  = '#023e8a'
C_GOLD  = '#ffd700'
C_RED   = '#cc0000'
C_BLACK = '#111111'
C_TEXT  = '#e9ecef'
C_GRAY  = '#aaaaaa'
C_GREEN = '#52b788'
C_DIM   = '#c8c8c8'
C_LIME  = '#a3e635'


# ── Card ───────────────────────────────────────────────────────────────────────
class Card:
    __slots__ = ('suit', 'rank')

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank

    def pts(self, trump: str) -> int:
        return TRUMP_PTS[self.rank] if self.suit == trump else PLAIN_PTS[self.rank]

    def power(self, trump: str, led: str) -> int:
        if self.suit == trump:
            return 200 + len(TRUMP_ORDER) - TRUMP_ORDER.index(self.rank)
        if self.suit == led:
            return 100 + len(PLAIN_ORDER) - PLAIN_ORDER.index(self.rank)
        return 0

    def __repr__(self):   return f"{self.rank}{self.suit}"
    def __eq__(self, o):  return isinstance(o, Card) and self.suit == o.suit and self.rank == o.rank
    def __hash__(self):   return hash((self.suit, self.rank))


def fresh_deck() -> List[Card]:
    return [Card(s, r) for s in SUITS for r in RANKS]


# ── Trick helpers ──────────────────────────────────────────────────────────────
def who_wins(trick: List[Tuple[int, Card]], trump: str) -> int:
    led = trick[0][1].suit
    bp, bc_pow = trick[0][0], trick[0][1].power(trump, led)
    for p, c in trick[1:]:
        pw = c.power(trump, led)
        if pw > bc_pow:
            bc_pow, bp = pw, p
    return bp


def legal_plays(hand: List[Card], trick: List[Tuple[int, Card]],
                trump: str, me: int) -> List[Card]:
    """Return legally playable cards (official Belote rules)."""
    if not trick:
        return list(hand)

    led    = trick[0][1].suit
    follow = [c for c in hand if c.suit == led]
    trumps = [c for c in hand if c.suit == trump]
    p_win  = who_wins(trick, trump) == (me + 2) % 4

    if follow:
        if led == trump:
            best = max(c.power(trump, led) for _, c in trick)
            hi   = [c for c in follow if c.power(trump, led) > best]
            return hi if hi else follow
        return follow

    if trumps and not p_win:
        best = max(
            (c.power(trump, led) for _, c in trick if c.suit == trump), default=0
        )
        hi = [c for c in trumps if c.power(trump, led) > best]
        return hi if hi else trumps

    return list(hand)


# ── AI ─────────────────────────────────────────────────────────────────────────
def _hand_score(hand: List[Card], trump: str) -> float:
    return (sum(TRUMP_PTS[c.rank] for c in hand if c.suit == trump)
            + sum(PLAIN_PTS[c.rank] for c in hand if c.suit != trump) * 0.25
            + sum(1 for c in hand if c.suit == trump) * 7)


def _is_master(card: Card, trump: str, played: set) -> bool:
    """True if no unplayed card can beat this card in its suit."""
    order = TRUMP_ORDER if card.suit == trump else PLAIN_ORDER
    idx   = order.index(card.rank)
    return all(Card(card.suit, r) in played for r in order[:idx])


def ai_bid_round1(hand: List[Card], revealed_card: Card) -> bool:
    """See AI_RULES.md – Bidding Round 1."""
    suit = revealed_card.suit
    # Rule 1: J is on the table → always take
    if revealed_card.rank == 'J':
        return True
    # Rule 2: AI holds the J of the offered suit → take
    if any(c.suit == suit and c.rank == 'J' for c in hand):
        return True
    # Rule 3: AI holds the 9 + ≥1 other trump → 3 trumps with revealed card
    trump_in_hand = sum(1 for c in hand if c.suit == suit)
    if any(c.suit == suit and c.rank == '9' for c in hand) and trump_in_hand >= 2:
        return True
    # Fallback: score heuristic
    return _hand_score(hand, suit) >= 58


def ai_bid_round2(hand: List[Card], revealed_suit: str) -> Optional[str]:
    """See AI_RULES.md – Bidding Round 2."""
    best_suit, best_score = None, 40
    for s in SUITS:
        if s == revealed_suit:
            continue
        sc = _hand_score(hand, s)
        if any(c.suit == s and c.rank == 'J' for c in hand):
            sc += 20
        trump_count = sum(1 for c in hand if c.suit == s)
        if any(c.suit == s and c.rank == '9' for c in hand) and trump_count >= 2:
            sc += 10
        if sc > best_score:
            best_score, best_suit = sc, s
    return best_suit


def ai_play(hand: List[Card], trick: List[Tuple[int, Card]],
            trump: str, me: int,
            played_cards: Optional[List[Card]] = None,
            contract_player: int = -1) -> Card:
    """See AI_RULES.md – Playing."""
    plays   = legal_plays(hand, trick, trump, me)
    played  = set(played_cards) if played_cards else set()
    partner = (me + 2) % 4
    partner_has_contract = (contract_player >= 0
                            and contract_player % 2 == me % 2
                            and contract_player != me)

    if not trick:
        # Priority 1: lead a master card (guaranteed win)
        masters = [c for c in plays if _is_master(c, trump, played)]
        if masters:
            return max(masters, key=lambda c: c.pts(trump))
        ts = [c for c in plays if c.suit == trump]
        # Priority 2: partner took contract → lead trump to drain opponents
        if partner_has_contract and ts:
            return max(ts, key=lambda c: c.power(trump, trump))
        # Priority 3: we took contract → lead trump aggressively
        if contract_player == me and ts:
            return max(ts, key=lambda c: c.power(trump, trump))
        # Default: highest point value — but avoid leading trump 9 while trump J is still live
        trump_j_out = any(c.suit == trump and c.rank == 'J' for c in played)
        safe = [c for c in plays
                if not (c.suit == trump and c.rank == '9' and not trump_j_out)]
        return max((safe or plays), key=lambda c: c.pts(trump))

    led   = trick[0][1].suit
    p_win = who_wins(trick, trump) == partner

    # Partner winning → give them points
    if p_win:
        return max(plays, key=lambda c: c.pts(trump))

    best = max(c.power(trump, led) for _, c in trick)
    win  = [c for c in plays if c.power(trump, led) > best]
    if win:
        return min(win, key=lambda c: c.power(trump, led))
    return min(plays, key=lambda c: c.pts(trump))


# ── Application ────────────────────────────────────────────────────────────────
class BeloteApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Belote")
        root.minsize(820, 580)
        root.configure(bg=BG_DARK)

        self.show_hints = tk.BooleanVar(value=True)

        # Live layout (updated on every redraw from canvas size)
        self.W  = DEFAULT_W
        self.H  = DEFAULT_H
        self.CX = DEFAULT_W // 2
        self.CY = int(DEFAULT_H * 0.455)

        # Persistent across rounds
        self.scores       = [0, 0]
        self.litige_pts   = 0
        self.round_num    = 0
        self.round_history: List[dict] = []

        # Bid-panel hover state
        self._bid_hover:       Optional[str]  = None
        self._bid_buttons:     dict           = {}
        self._bid_pass_flash:  bool           = False

        # Round state
        self.hands:           List[List[Card]] = [[], [], [], []]
        self.trump:           Optional[str]    = None
        self.revealed_card:   Optional[Card]   = None
        self.remaining_deck:  List[Card]       = []
        self.bid_round:       int              = 1
        self._bid_count:      int              = 0
        self.contract_player: int              = -1
        self.trick:              List[Tuple[int, Card]] = []
        self.played_cards:       List[Card]             = []
        self.last_trick_taken:   List[Optional[list]]   = [None, None]
        self.show_last_trick:    List[bool]             = [False, False]
        self.trick_pts:          List[int]              = [0, 0]
        self.tricks_won:      List[int]        = [0, 0]
        self.belote_player:   int              = -1
        self.belote_played:   int              = 0
        self.belote_pts:      List[int]        = [0, 0]
        self.dealer:          int              = 0
        self.current:         int              = 0
        self.selected:        Optional[Card]   = None
        self.phase:           str              = 'idle'
        self.round_info:      dict             = {}

        self._build_ui()
        self.root.after(400, self._new_round)

    # ── Layout ─────────────────────────────────────────────────────────────────
    def _update_layout(self):
        self.W  = max(self.cv.winfo_width(),  820)
        self.H  = max(self.cv.winfo_height(), 580)
        self.CX = self.W // 2
        self.CY = int(self.H * 0.455)

    @property
    def _trick_xy(self):
        cx, cy = self.CX, self.CY
        return {0: (cx, cy+90), 1: (cx+110, cy), 2: (cx, cy-90), 3: (cx-110, cy)}

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        self.cv = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.cv.pack(fill='both', expand=True)
        self.cv.bind('<Button-1>', self._on_canvas_click)
        self.cv.bind('<Configure>', lambda e: self._redraw())
        self.cv.bind('<Motion>', self._on_mouse_motion)
        self.cv.bind('<Leave>', self._on_mouse_leave)

        bar = tk.Frame(self.root, bg=BG_DARK, height=46)
        bar.pack(fill='x')
        bar.pack_propagate(False)

        tk.Checkbutton(bar, text='Show AI suggestions',
                       variable=self.show_hints, command=self._redraw,
                       bg=BG_DARK, fg=C_TEXT, selectcolor='#0a2218',
                       activebackground=BG_DARK, activeforeground=C_TEXT,
                       font=('Helvetica', 12)).pack(side='left', padx=18, pady=10)

        self.status = tk.Label(bar, text='', bg=BG_DARK, fg=C_GOLD,
                               font=('Helvetica', 12, 'bold'))
        self.status.pack(side='left', padx=18)

        tk.Button(bar, text='New Game', command=self._new_game,
                  bg='#991b1b', fg='white', relief='flat',
                  font=('Helvetica', 11, 'bold'), padx=12, pady=4,
                  cursor='hand2').pack(side='right', padx=18, pady=8)

    # ── Drawing primitives ─────────────────────────────────────────────────────
    def _rrect(self, x, y, w, h, r=8, **kw):
        pts = [x+r,y, x+w-r,y, x+w,y+r, x+w,y+h-r,
               x+w-r,y+h, x+r,y+h, x,y+h-r, x,y+r]
        self.cv.create_polygon(pts, smooth=True, **kw)

    def _draw_card_back(self, x, y, tags=()):
        self._rrect(x, y, CW, CH, fill=C_BACK, outline='#3a7bd5', width=1, tags=tags)
        for i in range(8, CW-8, 10):
            self.cv.create_line(x+i, y+5, x+i, y+CH-5,
                                fill='#1a5090', width=1, tags=tags)

    def _draw_card_face(self, x, y, card: Card, *,
                        highlight=False, dim=False, large=False, tags=()):
        bg  = C_DIM  if dim       else C_WHITE
        ol  = C_GOLD if highlight else ('#bbb' if dim else '#999')
        lw  = 3      if highlight else 1
        w   = CW + 10 if large else CW
        h   = CH + 14 if large else CH
        self._rrect(x, y, w, h, fill=bg, outline=ol, width=lw, tags=tags)
        ink = '#888' if dim else (C_RED if SUIT_RED[card.suit] else C_BLACK)
        f9  = ('Helvetica', 8, 'bold')
        f8  = ('Helvetica', 8)
        fsz = ('Helvetica', 24) if large else ('Helvetica', 20)
        self.cv.create_text(x+5,   y+4,    text=card.rank, fill=ink, font=f9, anchor='nw', tags=tags)
        self.cv.create_text(x+5,   y+15,   text=card.suit, fill=ink, font=f8, anchor='nw', tags=tags)
        self.cv.create_text(x+w//2,y+h//2, text=card.suit, fill=ink, font=fsz,anchor='center',tags=tags)
        self.cv.create_text(x+w-5, y+h-4,  text=card.rank, fill=ink, font=f9, anchor='se', tags=tags)
        self.cv.create_text(x+w-5, y+h-15, text=card.suit, fill=ink, font=f8, anchor='se', tags=tags)

    def _draw_mini_card(self, x, y, card: Card):
        sw, sh = 48, 66
        self._rrect(x, y, sw, sh, r=5, fill='#fffde8', outline=C_GOLD, width=2)
        ink = C_RED if SUIT_RED[card.suit] else C_BLACK
        self.cv.create_text(x+sw//2, y+sh//2-9, text=card.rank,
                            fill=ink, font=('Helvetica', 10, 'bold'), anchor='center')
        self.cv.create_text(x+sw//2, y+sh//2+9, text=card.suit,
                            fill=ink, font=('Helvetica', 13), anchor='center')

    # ── Main redraw ────────────────────────────────────────────────────────────
    def _redraw(self):
        self._update_layout()
        W, H, CX, CY = self.W, self.H, self.CX, self.CY
        self.cv.config(width=W, height=H)
        self.cv.delete('all')
        self._draw_table()
        self._draw_scores()
        self._draw_trick_area()
        self._draw_all_hands()
        self._draw_trick_stacks()
        self._draw_contract_chip()
        if self.show_hints.get() and self.phase == 'playing' and self.trump:
            self._draw_suggestions()
        if self.phase == 'bidding':
            self._draw_bid_panel()
        if self.phase == 'scoring':
            self._draw_score_overlay()
        if self.phase == 'gameover':
            self._draw_gameover_overlay()

    def _draw_table(self):
        W, H, CX, CY = self.W, self.H, self.CX, self.CY
        mg = 85   # side margin for player labels
        self.cv.create_oval(40, 30, W-40, H-20,
                            fill=BG, outline=C_GREEN, width=3)
        info = [
            (CX,              H-mg,  'YOU  (South)',          True),
            (W-SCORE_W-mg//2, CY,    'East  (AI)',             False),
            (CX,              50,    'North  (AI · partner)',  True),
        ]
        for x, y, label, partner in info:
            clr = C_LIME if partner else C_TEXT
            self.cv.create_text(x, y, text=label, fill=clr,
                                font=('Helvetica', 11, 'bold'), anchor='center')

        arrow_pos = {
            0: (CX,                   H-mg-20),
            1: (W-SCORE_W-mg//2-50,  CY),
            2: (CX,                   70),
            3: (mg+70,                CY),
        }
        if self.phase == 'playing' and self.current in arrow_pos:
            ax, ay = arrow_pos[self.current]
            self.cv.create_text(ax, ay, text='▶',
                                fill=C_GOLD, font=('Helvetica', 14))

        if self.trump:
            ink  = C_RED if SUIT_RED[self.trump] else C_TEXT
            team = 'You & North' if self.contract_player % 2 == 0 else 'East & West'
            self.cv.create_rectangle(8, 8, 240, 68, fill='#0a2218', outline=C_GREEN)
            self.cv.create_text(18, 18, anchor='nw',
                text=f'Atout / Trump: {self.trump}',
                fill=ink, font=('Helvetica', 13, 'bold'))
            self.cv.create_text(18, 42, anchor='nw',
                text=f'Preneurs / Takers: {team}',
                fill=C_GOLD, font=('Helvetica', 10))

        if self.belote_player >= 0 and self.belote_played > 0:
            msg       = 'Rebelote!' if self.belote_played >= 2 else 'Belote!'
            team_name = 'You & North' if self.belote_player % 2 == 0 else 'East & West'
            self.cv.create_text(18, 68, anchor='nw',
                text=f'{msg}  ({team_name})',
                fill='#ff9f40', font=('Helvetica', 10, 'bold'))

        if self.litige_pts > 0:
            self.cv.create_text(18, 86, anchor='nw',
                text=f'Litige: {self.litige_pts} pts in play',
                fill='#ffa0a0', font=('Helvetica', 10, 'italic'))

    def _draw_scores(self):
        W, H = self.W, self.H
        px, py = W - SCORE_W, 5
        ph = H - 10

        self.cv.create_rectangle(px, py, px + SCORE_W, py + ph,
                                 fill='#0a2218', outline=C_GREEN, width=2)

        # ── Header ──────────────────────────────────────────────────────────
        self.cv.create_text(px + SCORE_W // 2, py + 14,
                            text=f'FIRST TO {WIN_TARGET}',
                            fill=C_TEXT, font=('Helvetica', 10, 'bold'))

        # ── Team scores + progress bars ─────────────────────────────────────
        teams = [
            ('You & North', self.scores[0], C_LIME),
            ('East & West', self.scores[1], '#fca5a5'),
        ]
        bar_w  = SCORE_W - 20
        bar_x  = px + 10
        y      = py + 28
        for name, score, color in teams:
            # name + score on same row
            self.cv.create_text(bar_x, y, text=name,
                                fill=color, font=('Helvetica', 9, 'bold'), anchor='nw')
            self.cv.create_text(px + SCORE_W - 8, y, text=str(score),
                                fill=color, font=('Helvetica', 10, 'bold'), anchor='ne')
            y += 15
            # progress bar
            self.cv.create_rectangle(bar_x, y, bar_x + bar_w, y + 8,
                                     fill='#1b4332', outline='#2d6a4f', width=1)
            fill_px = int(bar_w * min(score, WIN_TARGET) / WIN_TARGET)
            if fill_px > 0:
                self.cv.create_rectangle(bar_x, y, bar_x + fill_px, y + 8,
                                         fill=color, outline='')
            y += 13

        # ── Points needed ───────────────────────────────────────────────────
        n0 = max(WIN_TARGET - self.scores[0], 0)
        n1 = max(WIN_TARGET - self.scores[1], 0)
        self.cv.create_text(px + SCORE_W // 2, y + 5,
                            text=f'Need  YN:{n0}  EW:{n1}',
                            fill=C_GRAY, font=('Helvetica', 8))
        y += 18

        # ── Separator ───────────────────────────────────────────────────────
        self.cv.create_line(px + 8, y, px + SCORE_W - 8, y,
                            fill=C_GREEN, width=1)
        y += 6

        # ── Round history header ─────────────────────────────────────────────
        self.cv.create_text(px + SCORE_W // 2, y + 7,
                            text=f'Round History  (#{self.round_num})',
                            fill=C_GRAY, font=('Helvetica', 9, 'bold'))
        y += 20

        # ── Per-round rows (newest first) ────────────────────────────────────
        RESULT_ICON = {
            'success': ('✓', C_LIME),
            'chute':   ('✗', '#ff6b6b'),
            'litige':  ('⚖', C_GOLD),
            'capot':   ('★', '#ff9f40'),
        }
        TEAM_SHORT = ['Y+N', 'E+W']
        row_h = 34

        for rnd in reversed(self.round_history):
            if y + row_h > py + ph - 4:
                break
            icon, icon_color = RESULT_ICON.get(rnd['result'], ('?', C_TEXT))
            ct_short = TEAM_SHORT[rnd['ct']]
            s0, s1   = rnd['scores_after']

            row_bg = '#0d2a1e' if rnd['round_num'] % 2 == 0 else '#081a11'
            self.cv.create_rectangle(px + 4, y, px + SCORE_W - 4, y + row_h - 2,
                                     fill=row_bg, outline='')

            # Round number
            self.cv.create_text(px + 12, y + 5,
                                text=f'#{rnd["round_num"]}',
                                fill=C_GRAY, font=('Helvetica', 8), anchor='nw')
            # Icon
            self.cv.create_text(px + 34, y + 5,
                                text=icon,
                                fill=icon_color, font=('Helvetica', 9, 'bold'), anchor='nw')
            # Taker label
            self.cv.create_text(px + 50, y + 5,
                                text=ct_short,
                                fill=icon_color, font=('Helvetica', 8, 'bold'), anchor='nw')
            # Points for this round
            self.cv.create_text(px + SCORE_W - 8, y + 5,
                                text=f'{rnd["taker_pts"]}–{rnd["def_pts"]}',
                                fill=C_DIM, font=('Helvetica', 8), anchor='ne')
            # Running total
            self.cv.create_text(px + 12, y + 19,
                                text=f'YN:{s0}  EW:{s1}',
                                fill=C_DIM, font=('Helvetica', 8), anchor='nw')
            y += row_h

    def _toggle_trick_reveal(self, team: int):
        self.show_last_trick[team] = not self.show_last_trick[team]
        self._redraw()

    def _draw_trick_stacks(self):
        W, H, CX, CY = self.W, self.H, self.CX, self.CY
        if not any(self.tricks_won):
            return

        # Team 0 (You+North): in front of South, bottom-left of centre
        # Team 1 (East+West):  in front of West, left side
        stack_pos = [
            (CX - CW - 60,  H - CH - 110),
            (148,            CY + 60),
        ]
        colors = [C_LIME, '#fca5a5']
        labels = ['You+N', 'E+W']

        for team, (sx, sy) in enumerate(stack_pos):
            n = self.tricks_won[team]
            if n == 0:
                continue

            depth = min(n, 4)
            # Stacked card backs (depth effect)
            for i in range(depth):
                off = (depth - 1 - i) * 4
                self._draw_card_back(sx + off, sy - off)

            # Trick-count badge
            bx = sx + CW + (depth - 1) * 4 - 6
            by = sy - (depth - 1) * 4 - 8
            self.cv.create_oval(bx, by, bx + 20, by + 20,
                                fill='#991b1b', outline='white', width=1)
            self.cv.create_text(bx + 10, by + 10, text=str(n),
                                fill='white', font=('Helvetica', 8, 'bold'))

            # Label + click hint
            mid_x = sx + CW // 2 + (depth - 1) * 2
            self.cv.create_text(mid_x, sy + CH + 12, text=labels[team],
                                fill=colors[team], font=('Helvetica', 8, 'bold'))
            hint = '▲ close' if self.show_last_trick[team] else '▼ peek'
            self.cv.create_text(mid_x, sy + CH + 24, text=hint,
                                fill=C_GRAY, font=('Helvetica', 7))

            # Invisible click region
            tag = f'tstack_{team}'
            self.cv.create_rectangle(
                sx - 2, sy - (depth - 1) * 4 - 2,
                sx + CW + (depth - 1) * 4 + 2, sy + CH + 2,
                fill='', outline='', tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>',
                             lambda e, t=team: self._toggle_trick_reveal(t))

            # Last-trick reveal panel
            if self.show_last_trick[team] and self.last_trick_taken[team]:
                self._draw_last_trick_panel(sx, sy, team, depth)

    def _draw_last_trick_panel(self, sx, sy, team: int, depth: int):
        last  = self.last_trick_taken[team]
        mw, mh, gap = 48, 66, 6
        pw = len(last) * (mw + gap) - gap + 20
        ph = mh + 46

        if team == 0:
            px = sx - (pw - CW) // 2 - (depth - 1) * 2
            py = sy - ph - 10
        else:
            px = sx + CW + (depth - 1) * 4 + 14
            py = sy - ph // 2 + CH // 2

        # Clamp to visible canvas area
        px = max(4, min(px, self.W - SCORE_W - pw - 4))
        py = max(4, py)

        self._rrect(px, py, pw, ph, r=8, fill='#0a2218', outline=C_GOLD, width=2)
        self.cv.create_text(px + pw // 2, py + 12,
                            text='Last trick', fill=C_GOLD,
                            font=('Helvetica', 9, 'bold'))

        for i, (pidx, card) in enumerate(last):
            cx = px + 10 + i * (mw + gap)
            cy = py + 22
            self._draw_mini_card(cx, cy, card)
            self.cv.create_text(cx + mw // 2, cy + mh + 9,
                                text=PLAYER_NAMES[pidx][:3],
                                fill=C_GRAY, font=('Helvetica', 7))

    def _draw_trick_area(self):
        CX, CY = self.CX, self.CY
        self.cv.create_oval(CX-105, CY-110, CX+105, CY+110,
                            fill='', outline=C_GREEN, width=1, dash=(4, 4))

        if self.revealed_card and self.phase == 'bidding':
            rx = CX - (CW+10)//2
            ry = CY - (CH+14)//2
            self.cv.create_text(CX, ry-14, text='Carte retournée',
                                fill=C_GOLD, font=('Helvetica', 9, 'italic'))
            self._draw_card_face(rx, ry, self.revealed_card, large=True)

        for pidx, card in self.trick:
            cx, cy = self._trick_xy[pidx]
            self._draw_card_face(cx - CW//2, cy - CH//2, card)

        if self.trick_pts[0] or self.trick_pts[1]:
            self.cv.create_text(
                CX, CY-125,
                text=(f'Pts in hand:  '
                      f'You+N={self.trick_pts[0]}  '
                      f'E+W={self.trick_pts[1]}'),
                fill=C_GRAY, font=('Helvetica', 10))

    def _draw_all_hands(self):
        W, H, CX = self.W, self.H, self.CX
        hand = self.hands[0]
        n    = len(hand)
        if n:
            playable = (legal_plays(hand, self.trick, self.trump, 0)
                        if self.phase == 'playing' and self.current == 0 and self.trump
                        else [])
            avail  = W - 120
            spread = min(CW + 6, avail // max(n, 1))
            sx = CX - (spread * (n-1) + CW) // 2
            y  = H - CH - 18
            for i, card in enumerate(hand):
                x   = sx + i * spread
                hl  = card == self.selected
                dim = bool(playable) and card not in playable
                self._draw_card_face(x, y, card, highlight=hl, dim=dim,
                                     tags=(f'hcard_{i}',))

        self._draw_ai_back(2, 'top')
        self._draw_ai_back(1, 'right')
        self._draw_ai_back(3, 'left')
        mg = 85
        self.cv.create_text(mg, self.CY, text='West  (AI)', fill=C_TEXT,
                            font=('Helvetica', 11, 'bold'), anchor='center')

    def _draw_ai_back(self, pidx: int, pos: str):
        W, H, CX, CY = self.W, self.H, self.CX, self.CY
        n = len(self.hands[pidx])
        if n == 0:
            return
        if pos == 'top':
            avail  = W - 160
            spread = min(CW + 6, avail // max(n, 1))
            sx = CX - (spread*(n-1) + CW) // 2
            for i in range(n):
                self._draw_card_back(sx + i*spread, 68)
        elif pos == 'right':
            avail  = H - 250
            spread = min(CH + 4, avail // max(n, 1))
            sy = CY - (spread*(n-1) + CH) // 2
            for i in range(n):
                self._draw_card_back(W - SCORE_W - CW - 12, sy + i*spread)
        elif pos == 'left':
            avail  = H - 250
            spread = min(CH + 4, avail // max(n, 1))
            sy = CY - (spread*(n-1) + CH) // 2
            for i in range(n):
                self._draw_card_back(70, sy + i*spread)

    def _draw_contract_chip(self):
        if self.contract_player < 0 or not self.trump:
            return
        W, H, CX, CY = self.W, self.H, self.CX, self.CY
        mg = 85
        chip_pos = {
            0: (CX + 80,                    H - mg),
            1: (W - SCORE_W - mg // 2 + 55, CY - 18),
            2: (CX + 80,                    55),
            3: (mg + CW + 30,               CY),
        }
        cpx, cpy = chip_pos[self.contract_player]
        r = 11
        self.cv.create_oval(cpx - r, cpy - r, cpx + r, cpy + r,
                            fill='#1a1a1a', outline=C_GOLD, width=3)
        self.cv.create_text(cpx, cpy, text='C',
                            fill=C_GOLD, font=('Helvetica', 9, 'bold'))

    def _draw_suggestions(self):
        hand = self.hands[0]
        if not hand or not self.trump or self.phase != 'playing' or self.current != 0:
            return
        suggestion = ai_play(hand, self.trick, self.trump, 0,
                             self.played_cards, self.contract_player)
        W, H, CX = self.W, self.H, self.CX
        n      = len(hand)
        avail  = W - 120
        spread = min(CW + 6, avail // max(n, 1))
        sx0    = CX - (spread * (n - 1) + CW) // 2
        y      = H - CH - 18
        for i, card in enumerate(hand):
            if card == suggestion:
                cx = sx0 + i * spread + CW // 2
                self.cv.create_text(cx, y - 16, text='★',
                                    fill=C_GOLD, font=('Helvetica', 11, 'bold'))
                break

    # ── Hover handling ─────────────────────────────────────────────────────────
    def _on_mouse_motion(self, event):
        if self.phase != 'bidding' or self.current != 0:
            if self._bid_hover is not None:
                self._bid_hover = None
                self.cv.config(cursor='')
            return
        new_hover = None
        for name, (x1, y1, x2, y2) in self._bid_buttons.items():
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                new_hover = name
                break
        self.cv.config(cursor='hand2' if new_hover else '')
        if new_hover != self._bid_hover:
            self._bid_hover = new_hover
            self._redraw()

    def _on_mouse_leave(self, event):
        if self._bid_hover is not None:
            self._bid_hover = None
            self.cv.config(cursor='')
            self._redraw()

    # ── Bid panel ──────────────────────────────────────────────────────────────
    def _btn_style(self, name: str, normal_fill: str, normal_ol: str,
                   hover_fill: str, hover_ol: str):
        """Return (fill, outline) for a bid button, brightened when hovered."""
        if self._bid_hover == name:
            return hover_fill, hover_ol
        return normal_fill, normal_ol

    def _draw_bid_panel(self):
        W, H, CX = self.W, self.H, self.CX
        hand_y = H - CH - 18
        ph     = 120
        py     = hand_y - ph - 12
        pw     = min(680, W - 80)
        px     = (W - pw) // 2

        self._bid_buttons.clear()

        self._rrect(px, py, pw, ph, r=12,
                    fill='#0a2218', outline=C_GREEN, width=2)

        if self.bid_round == 1:
            suit = self.revealed_card.suit
            self.cv.create_text(px+pw//2, py+16,
                text=f'Tour de prise  –  Round 1 of 2  '
                     f'(accept {suit} as trump, or pass)',
                fill=C_TEXT, font=('Helvetica', 11, 'bold'))

            btn_w = min(160, pw // 2 - 30)
            btn_h = 52
            btn_y = py + ph//2 - btn_h//2 + 8

            # Take button – green, positive action
            bx = px + pw//4 - btn_w//2
            fill, ol = self._btn_style('bid_take',
                                       '#1b4332', C_GOLD,
                                       '#2d8a58', '#ffe44d')
            tag = 'bid_take'
            self._rrect(bx, btn_y, btn_w, btn_h, r=8,
                        fill=fill, outline=ol, width=2, tags=(tag,))
            self.cv.create_text(px + pw//4, btn_y + btn_h//2,
                text=f'Take  {suit}', fill=C_TEXT,
                font=('Helvetica', 14, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>', lambda e: self._on_bid_take(None))
            self._bid_buttons[tag] = (bx, btn_y, bx + btn_w, btn_y + btn_h)

            # Pass button – dark maroon, clearly clickable but declining
            bx = px + 3*pw//4 - btn_w//2
            fill, ol = self._btn_style('bid_pass',
                                       '#3d1818', '#c03030',
                                       '#5c2222', '#e84040')
            tag = 'bid_pass'
            self._rrect(bx, btn_y, btn_w, btn_h, r=8,
                        fill=fill, outline=ol, width=2, tags=(tag,))
            self.cv.create_text(px + 3*pw//4, btn_y + btn_h//2,
                text='Pass', fill=C_TEXT,
                font=('Helvetica', 14, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>', lambda e: self._on_bid_pass())
            self._bid_buttons[tag] = (bx, btn_y, bx + btn_w, btn_y + btn_h)

        else:
            revealed = self.revealed_card.suit
            other    = [s for s in SUITS if s != revealed]
            self.cv.create_text(px+pw//2, py+16,
                text=f'Tour de prise  –  Round 2  '
                     f'(choose trump, not {revealed})',
                fill=C_TEXT, font=('Helvetica', 11, 'bold'))

            n_btns  = 4
            btn_w   = min(120, (pw - 40) // n_btns - 8)
            btn_h   = 52
            btn_y   = py + ph//2 - btn_h//2 + 8
            total_w = n_btns * btn_w + (n_btns - 1) * 12
            bx0     = px + (pw - total_w) // 2

            for i, s in enumerate(other):
                bx  = bx0 + i * (btn_w + 12)
                ink = C_RED if SUIT_RED[s] else C_BLACK
                tag = f'bid_suit_{s}'
                fill, ol = self._btn_style(tag,
                                           '#fefae0', C_GOLD,
                                           '#fff8b0', '#ffe44d')
                self._rrect(bx, btn_y, btn_w, btn_h, r=8,
                            fill=fill, outline=ol, width=2, tags=(tag,))
                self.cv.create_text(bx + btn_w//2, btn_y + btn_h//2,
                    text=s, fill=ink,
                    font=('Helvetica', 24), tags=(tag,))
                self.cv.tag_bind(tag, '<Button-1>',
                                 lambda e, suit=s: self._on_bid_take(suit))
                self._bid_buttons[tag] = (bx, btn_y, bx + btn_w, btn_y + btn_h)

            # Pass button (round 2)
            bx  = bx0 + 3 * (btn_w + 12)
            fill, ol = self._btn_style('bid_pass2',
                                       '#3d1818', '#c03030',
                                       '#5c2222', '#e84040')
            tag = 'bid_pass2'
            self._rrect(bx, btn_y, btn_w, btn_h, r=8,
                        fill=fill, outline=ol, width=2, tags=(tag,))
            self.cv.create_text(bx + btn_w//2, btn_y + btn_h//2,
                text='Pass', fill=C_TEXT,
                font=('Helvetica', 13, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>', lambda e: self._on_bid_pass())
            self._bid_buttons[tag] = (bx, btn_y, bx + btn_w, btn_y + btn_h)

        if self._bid_pass_flash:
            self._rrect(px + pw//2 - 90, py + 20, 180, 80, r=10,
                        fill='#1b4332', outline=C_LIME, width=3)
            self.cv.create_text(px + pw//2, py + 60,
                text='Passed  ✓', fill=C_LIME,
                font=('Helvetica', 16, 'bold'))

    # ── Score overlay ──────────────────────────────────────────────────────────
    def _draw_score_overlay(self):
        W, H = self.W, self.H
        ri = self.round_info
        ct, at = ri.get('ct', 0), ri.get('at', 1)
        result = ri.get('result', '')

        result_labels = {
            'success': ('Contrat réussi  ✓', C_LIME),
            'chute':   ('Chute  ✗  (contract failed)', '#ff6b6b'),
            'litige':  ('Litige  ⚖  (81 – 81 tie)', C_GOLD),
            'capot':   ('Capot  ★  (all 8 tricks!)', '#ff9f40'),
        }
        res_text, res_color = result_labels.get(result, ('', C_TEXT))
        team_names = ['You & North', 'East & West']

        ow, oh = min(480, W - 40), 400
        ox = (W - ow) // 2
        oy = (H - oh) // 2
        self._rrect(ox, oy, ow, oh, r=16, fill='#0a2218', outline=C_GOLD, width=3)

        self.cv.create_text(ox+ow//2, oy+24,
                            text='Round over', fill=C_GOLD,
                            font=('Helvetica', 15, 'bold'))
        self.cv.create_text(ox+ow//2, oy+52,
                            text=res_text, fill=res_color,
                            font=('Helvetica', 13, 'bold'))

        trump_ink = C_RED if self.trump and SUIT_RED[self.trump] else C_BLACK
        lines = [
            (f"Trump: {self.trump}  |  Takers: {team_names[ct]}", trump_ink),
            ('', C_TEXT),
            (f"{team_names[ct]}  tricks pts: {ri.get('taker_trick_pts', 0)}", C_TEXT),
            (f"{team_names[at]}  tricks pts: {ri.get('def_trick_pts', 0)}", C_TEXT),
        ]
        if ri.get('belote_team') is not None:
            bteam = team_names[ri['belote_team']]
            lines.append((f"Belote: {bteam} +20 pts  (imprenable)", '#ff9f40'))
        lines += [
            ('', C_TEXT),
            (f"{team_names[ct]}  total: {ri.get('taker_pts', 0)}", C_TEXT),
            (f"{team_names[at]}  total: {ri.get('def_pts', 0)}", C_TEXT),
        ]
        if result == 'litige':
            lines.append((f"Litige: {ri.get('litige_after', 0)} pts carried over", '#ffa0a0'))

        for i, (ln, clr) in enumerate(lines):
            self.cv.create_text(ox+ow//2, oy+80 + i*22,
                                text=ln, fill=clr, font=('Helvetica', 11))

        sep_y = oy + 80 + len(lines) * 22 + 6
        self.cv.create_line(ox+30, sep_y, ox+ow-30, sep_y,
                            fill='#2d6a4f', width=1)
        self.cv.create_text(ox+ow//2, sep_y+14,
                            text='Running scores:', fill=C_GRAY,
                            font=('Helvetica', 10))
        self.cv.create_text(ox+ow//2, sep_y+32,
                            text=f'You & North: {self.scores[0]}   '
                                 f'East & West: {self.scores[1]}',
                            fill=C_TEXT, font=('Helvetica', 11, 'bold'))

        tag = 'next_round'
        self._rrect(ox+ow//2-70, oy+oh-44, 140, 34, r=8,
                    fill='#991b1b', outline=C_GOLD, width=2, tags=(tag,))
        self.cv.create_text(ox+ow//2, oy+oh-27,
                            text='Next round ▶', fill='white',
                            font=('Helvetica', 12, 'bold'), tags=(tag,))
        self.cv.tag_bind(tag, '<Button-1>', lambda e: self._new_round())

    def _draw_gameover_overlay(self):
        W, H = self.W, self.H
        winner = 0 if self.scores[0] > self.scores[1] else 1
        team   = ['You & North', 'East & West'][winner]
        color  = C_LIME if winner == 0 else '#fca5a5'

        ow, oh = min(440, W - 40), 280
        ox = (W - ow) // 2
        oy = (H - oh) // 2
        self._rrect(ox, oy, ow, oh, r=16, fill='#0a2218', outline=C_GOLD, width=3)
        self.cv.create_text(ox+ow//2, oy+36,
                            text='Game Over', fill=C_GOLD,
                            font=('Helvetica', 18, 'bold'))
        self.cv.create_text(ox+ow//2, oy+80,
                            text=f'  {team} win!', fill=color,
                            font=('Helvetica', 15, 'bold'))
        self.cv.create_text(ox+ow//2, oy+120,
                            text=f'Final: You & North {self.scores[0]}   '
                                 f'East & West {self.scores[1]}',
                            fill=C_TEXT, font=('Helvetica', 12))

        tag = 'new_game_btn'
        self._rrect(ox+ow//2-80, oy+oh-54, 160, 38, r=8,
                    fill='#991b1b', outline=C_GOLD, width=2, tags=(tag,))
        self.cv.create_text(ox+ow//2, oy+oh-35,
                            text='New Game', fill='white',
                            font=('Helvetica', 13, 'bold'), tags=(tag,))
        self.cv.tag_bind(tag, '<Button-1>', lambda e: self._new_game())

    # ── Game flow ──────────────────────────────────────────────────────────────
    def _new_game(self):
        self.scores        = [0, 0]
        self.litige_pts    = 0
        self.round_num     = 0
        self.round_history = []
        self.dealer        = 0
        self._new_round()

    def _new_round(self):
        deck  = fresh_deck()
        random.shuffle(deck)
        start = (self.dealer + 1) % 4
        for i in range(4):
            pidx = (start + i) % 4
            self.hands[pidx] = deck[i*5 : i*5+5]

        self.revealed_card  = deck[20]
        self.remaining_deck = deck[21:]

        self.trump              = None
        self.contract_player    = -1
        self.trick              = []
        self.played_cards       = []
        self.last_trick_taken   = [None, None]
        self.show_last_trick    = [False, False]
        self.trick_pts          = [0, 0]
        self.tricks_won      = [0, 0]
        self.belote_player   = -1
        self.belote_played   = 0
        self.belote_pts      = [0, 0]
        self.selected        = None
        self.bid_round       = 1
        self._bid_count      = 0
        self.round_info      = {}
        self.current         = start
        self.phase           = 'bidding'

        self.status.config(text='Bidding phase – round 1')
        self._redraw()
        if self.current != 0:
            self.root.after(700, self._ai_bid_step)

    def _deal_remaining(self, taker_idx: int):
        start = (self.dealer + 1) % 4
        idx   = 0
        for i in range(4):
            pidx = (start + i) % 4
            if pidx == taker_idx:
                self.hands[pidx].append(self.revealed_card)
                self.hands[pidx].extend(self.remaining_deck[idx:idx+2])
                idx += 2
            else:
                self.hands[pidx].extend(self.remaining_deck[idx:idx+3])
                idx += 3

    def _detect_belote(self):
        self.belote_player = -1
        self.belote_played = 0
        for pidx in range(4):
            has_k = any(c.suit == self.trump and c.rank == 'K' for c in self.hands[pidx])
            has_q = any(c.suit == self.trump and c.rank == 'Q' for c in self.hands[pidx])
            if has_k and has_q:
                self.belote_player = pidx
                break

    # ── Bidding flow ───────────────────────────────────────────────────────────
    def _ai_bid_step(self):
        if self.phase != 'bidding' or self.current == 0:
            return
        pidx = self.current
        if self.bid_round == 1:
            if ai_bid_round1(self.hands[pidx], self.revealed_card):
                self._apply_take(pidx, None)
            else:
                self._apply_pass(pidx)
        else:
            suit = ai_bid_round2(self.hands[pidx], self.revealed_card.suit)
            if suit:
                self._apply_take(pidx, suit)
            else:
                self._apply_pass(pidx)

    def _apply_take(self, pidx: int, suit: Optional[str]):
        trump = suit if suit else self.revealed_card.suit
        self.trump           = trump
        self.contract_player = pidx
        self.status.config(
            text=f'{PLAYER_NAMES[pidx]} takes with {trump}  '
                 f'({"round 1" if self.bid_round == 1 else "round 2"})')
        self._deal_remaining(pidx)
        self._detect_belote()
        self._start_play()

    def _apply_pass(self, pidx: int):
        self._bid_count += 1
        self.status.config(text=f'{PLAYER_NAMES[pidx]} passes')

        if self._bid_count == 4:
            if self.bid_round == 1:
                self.bid_round  = 2
                self._bid_count = 0
                self.current    = (self.dealer + 1) % 4
                self.status.config(text='Bidding phase – round 2')
                self._redraw()
                if self.current != 0:
                    self.root.after(700, self._ai_bid_step)
            else:
                self.dealer = (self.dealer + 1) % 4
                self.status.config(text='No takers – redealing…')
                self._redraw()
                self.root.after(1200, self._new_round)
            return

        self.current = (pidx + 1) % 4
        self._redraw()
        if self.current != 0:
            self.root.after(700, self._ai_bid_step)

    def _on_bid_take(self, suit: Optional[str]):
        self._apply_take(0, suit)

    def _on_bid_pass(self):
        self._bid_pass_flash = True
        self._redraw()
        self.root.after(280, self._execute_bid_pass)

    def _execute_bid_pass(self):
        self._bid_pass_flash = False
        self._apply_pass(0)

    # ── Play flow ──────────────────────────────────────────────────────────────
    def _start_play(self):
        self.phase   = 'playing'
        self.trick   = []
        self.current = (self.dealer + 1) % 4
        self.status.config(text=f'Playing  –  trump: {self.trump}')
        self._redraw()
        if self.current != 0:
            self.root.after(800, self._ai_play_step)

    def _ai_play_step(self):
        if self.phase != 'playing' or self.current == 0:
            return
        card = ai_play(self.hands[self.current], self.trick,
                       self.trump, self.current,
                       self.played_cards, self.contract_player)
        self._play_card(self.current, card)

    def _play_card(self, pidx: int, card: Card):
        self.hands[pidx].remove(card)
        self._check_belote_play(pidx, card)
        self.trick.append((pidx, card))
        if len(self.trick) == 4:
            self._redraw()
            self.root.after(1100, self._finish_trick)
        else:
            self.current = (pidx + 1) % 4
            self._redraw()
            if self.current != 0:
                self.root.after(750, self._ai_play_step)

    def _check_belote_play(self, pidx: int, card: Card):
        if pidx != self.belote_player:
            return
        if card.suit != self.trump or card.rank not in ('K', 'Q'):
            return
        self.belote_played += 1
        self.belote_pts[pidx % 2] = 20
        word = 'Rebelote!' if self.belote_played >= 2 else 'Belote!'
        self.status.config(text=f'{word}  ({PLAYER_NAMES[pidx]})')

    def _finish_trick(self):
        winner = who_wins(self.trick, self.trump)
        team   = winner % 2
        pts    = sum(c.pts(self.trump) for _, c in self.trick)
        self.trick_pts[team]  += pts
        self.tricks_won[team] += 1

        for _, card in self.trick:
            self.played_cards.append(card)
        self.last_trick_taken[team] = list(self.trick)

        is_last = not self.hands[0]
        if is_last:
            capot = (self.tricks_won[1 - team] == 0)
            self.trick_pts[team] += 100 if capot else 10

        if is_last:
            self.current = winner
            self.phase   = 'last_trick'
            self.status.config(text='Click anywhere to continue ▶')
            self._redraw()
        else:
            self.trick   = []
            self.current = winner
            self.status.config(text=f'{PLAYER_NAMES[winner]} wins the trick')
            self._redraw()
            if self.current != 0:
                self.root.after(750, self._ai_play_step)

    def _finish_round(self):
        ct = self.contract_player % 2
        at = 1 - ct

        taker_trick = self.trick_pts[ct]
        def_trick   = self.trick_pts[at]
        taker_pts   = taker_trick + self.belote_pts[ct]
        def_pts     = def_trick   + self.belote_pts[at]

        all_to_ct = (self.tricks_won[at] == 0)
        all_to_at = (self.tricks_won[ct] == 0)

        belote_team = (self.belote_player % 2
                       if self.belote_player >= 0 and self.belote_played > 0
                       else None)

        if all_to_ct or all_to_at:
            w, l   = (ct, at) if all_to_ct else (at, ct)
            result = 'capot'
            self.scores[w] += taker_pts + def_pts - self.belote_pts[l] + self.litige_pts
            self.scores[l] += self.belote_pts[l]
            self.litige_pts = 0
        elif taker_pts > def_pts:
            result = 'success'
            self.scores[ct] += taker_pts + self.litige_pts
            self.scores[at] += def_pts
            self.litige_pts  = 0
        elif taker_pts == def_pts:
            result = 'litige'
            self.scores[at] += def_pts
            self.litige_pts += taker_pts
        else:
            result = 'chute'
            self.scores[ct] += self.belote_pts[ct]
            self.scores[at] += 162 + self.belote_pts[at] + self.litige_pts
            self.litige_pts  = 0

        self.round_num += 1
        self.round_info = {
            'result':          result,
            'ct':              ct,
            'at':              at,
            'taker_trick_pts': taker_trick,
            'def_trick_pts':   def_trick,
            'taker_pts':       taker_pts,
            'def_pts':         def_pts,
            'belote_team':     belote_team,
            'litige_after':    self.litige_pts,
        }
        self.round_history.append({
            'round_num':    self.round_num,
            'result':       result,
            'ct':           ct,
            'taker_pts':    taker_pts,
            'def_pts':      def_pts,
            'scores_after': list(self.scores),
        })

        self.dealer = (self.dealer + 1) % 4
        self.status.config(text='Round over – see results')
        self.phase = 'gameover' if max(self.scores) >= WIN_TARGET else 'scoring'
        self._redraw()

    # ── Click handling ─────────────────────────────────────────────────────────
    def _on_canvas_click(self, event):
        if self.phase == 'last_trick':
            self.trick = []
            self._finish_round()
            return
        if self.phase != 'playing' or self.current != 0:
            return
        hand = self.hands[0]
        n    = len(hand)
        if n == 0:
            return
        W   = self.W
        avail  = W - 120
        spread = min(CW + 6, avail // max(n, 1))
        sx = self.CX - (spread * (n-1) + CW) // 2
        y  = self.H - CH - 18
        for i, card in enumerate(hand):
            cx = sx + i * spread
            if cx <= event.x <= cx + CW and y <= event.y <= y + CH:
                self._handle_human_card(card)
                return

    def _handle_human_card(self, card: Card):
        hand     = self.hands[0]
        playable = legal_plays(hand, self.trick, self.trump, 0)
        if card not in playable:
            return
        if self.selected == card:
            self._play_card(0, card)
            self.selected = None
        else:
            self.selected = card
            self._redraw()


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    BeloteApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
