#!/usr/bin/env python3
"""Belote – French trick-taking card game
4 players: You (South) + 3 AI  |  Teams: South+North vs East+West
"""
import tkinter as tk
import random
from typing import List, Tuple, Optional

# ── Constants ──────────────────────────────────────────────────────────────────
SUITS      = ['♠', '♥', '♦', '♣']
SUIT_RED   = {'♠': False, '♥': True, '♦': True, '♣': False}
RANKS      = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']

TRUMP_ORDER = ['J', '9', 'A', '10', 'K', 'Q', '8', '7']   # 0 = strongest
PLAIN_ORDER = ['A', '10', 'K', 'Q', 'J', '9', '8', '7']

TRUMP_PTS = {'J': 20, '9': 14, 'A': 11, '10': 10, 'K': 4, 'Q': 3, '8': 0, '7': 0}
PLAIN_PTS = {'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0, '8': 0, '7': 0}

CW, CH = 68, 96        # card width / height
W,  H  = 1060, 740     # window
CX, CY = 510, 340      # table centre

BG        = '#2d6a4f'
BG_DARK   = '#1b4332'
C_WHITE   = '#fefae0'
C_BACK    = '#023e8a'
C_GOLD    = '#ffd700'
C_RED     = '#cc0000'
C_BLACK   = '#111111'
C_TEXT    = '#e9ecef'
C_GRAY    = '#aaaaaa'
C_GREEN   = '#52b788'
C_DIM     = '#c8c8c8'
C_LIME    = '#a3e635'

# Where each player's trick card is placed (centre of card)
TRICK_XY = {0: (CX, CY+90), 1: (CX+100, CY), 2: (CX, CY-90), 3: (CX-100, CY)}

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
    if not trick:
        return list(hand)

    led     = trick[0][1].suit
    follow  = [c for c in hand if c.suit == led]
    trumps  = [c for c in hand if c.suit == trump]
    partner = (me + 2) % 4
    p_win   = who_wins(trick, trump) == partner

    if follow:
        if led == trump:
            best = max(c.power(trump, led) for _, c in trick)
            hi   = [c for c in follow if c.power(trump, led) > best]
            return hi if hi else follow
        return follow

    if trumps and not p_win:
        best = max((c.power(trump, led) for _, c in trick if c.suit == trump), default=0)
        hi   = [c for c in trumps if c.power(trump, led) > best]
        return hi if hi else trumps

    return list(hand)


# ── AI ─────────────────────────────────────────────────────────────────────────
def ai_bid(hand: List[Card], current_bid: int) -> Tuple[Optional[int], Optional[str]]:
    best_suit, best_score = SUITS[0], -1
    for suit in SUITS:
        score = (sum(TRUMP_PTS[c.rank] for c in hand if c.suit == suit)
                 + sum(PLAIN_PTS[c.rank] for c in hand if c.suit != suit) * 0.25
                 + sum(1 for c in hand if c.suit == suit) * 7)
        if score > best_score:
            best_score, best_suit = score, suit

    if best_score < 55:  return None, None
    bid = 80  if best_score < 65 else \
          90  if best_score < 74 else \
          100 if best_score < 85 else \
          110 if best_score < 96 else 120

    bid = max(bid, current_bid + 10)
    return (None, None) if bid > 160 else (bid, best_suit)


def ai_play(hand: List[Card], trick: List[Tuple[int, Card]],
            trump: str, me: int) -> Card:
    plays = legal_plays(hand, trick, trump, me)

    if not trick:
        ts = [c for c in plays if c.suit == trump]
        if ts: return max(ts, key=lambda c: c.power(trump, trump))
        return max(plays, key=lambda c: c.pts(trump))

    led     = trick[0][1].suit
    p_win   = who_wins(trick, trump) == (me + 2) % 4
    if p_win:
        return max(plays, key=lambda c: c.pts(trump))

    best = max(c.power(trump, led) for _, c in trick)
    win  = [c for c in plays if c.power(trump, led) > best]
    if win: return min(win, key=lambda c: c.power(trump, led))
    return min(plays, key=lambda c: c.pts(trump))


# ── Application ────────────────────────────────────────────────────────────────
class BeloteApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Belote")
        root.resizable(False, False)
        root.configure(bg=BG_DARK)

        self.show_hints = tk.BooleanVar(value=True)

        # persistent scores across rounds
        self.scores = [0, 0]

        # round state
        self.hands:           List[List[Card]] = [[], [], [], []]
        self.trump:           Optional[str]    = None
        self.contract:        int              = 0
        self.contract_player: int              = -1
        self.trick:           List[Tuple[int, Card]] = []
        self.trick_pts:       List[int]        = [0, 0]
        self.tricks_won:      List[int]        = [0, 0]
        self.dealer:          int              = 0
        self.current:         int              = 0

        # bidding
        self.bid_passes:      int              = 0
        self.pending_val:     Optional[int]    = None   # awaiting suit pick

        # play
        self.selected:        Optional[Card]   = None
        self.phase:           str              = 'idle'

        self._build_ui()
        self.root.after(400, self._new_round)

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        self.cv = tk.Canvas(self.root, width=W, height=H,
                            bg=BG, highlightthickness=0)
        self.cv.pack()
        self.cv.bind('<Button-1>', self._on_canvas_click)

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
            self.cv.create_line(x+i, y+5, x+i, y+CH-5, fill='#1a5090', width=1, tags=tags)

    def _draw_card_face(self, x, y, card: Card, *,
                        highlight=False, dim=False, tags=()):
        bg  = C_DIM   if dim       else C_WHITE
        ol  = C_GOLD  if highlight else ('#bbb' if dim else '#999')
        lw  = 3       if highlight else 1
        self._rrect(x, y, CW, CH, fill=bg, outline=ol, width=lw, tags=tags)
        ink = '#888' if dim else (C_RED if SUIT_RED[card.suit] else C_BLACK)
        f9  = ('Helvetica', 8,  'bold')
        f8  = ('Helvetica', 8)
        f22 = ('Helvetica', 20)
        nw, se = 'nw', 'se'
        self.cv.create_text(x+5,    y+4,       text=card.rank,  fill=ink, font=f9, anchor=nw, tags=tags)
        self.cv.create_text(x+5,    y+15,      text=card.suit,  fill=ink, font=f8, anchor=nw, tags=tags)
        self.cv.create_text(x+CW//2,y+CH//2,   text=card.suit,  fill=ink, font=f22,anchor='center',tags=tags)
        self.cv.create_text(x+CW-5, y+CH-4,    text=card.rank,  fill=ink, font=f9, anchor=se, tags=tags)
        self.cv.create_text(x+CW-5, y+CH-15,   text=card.suit,  fill=ink, font=f8, anchor=se, tags=tags)

    def _draw_mini_card(self, x, y, card: Card):
        """Small preview card for AI hints."""
        sw, sh = 48, 66
        self._rrect(x, y, sw, sh, r=5, fill='#fffde8', outline=C_GOLD, width=2)
        ink = C_RED if SUIT_RED[card.suit] else C_BLACK
        self.cv.create_text(x+sw//2, y+sh//2-9, text=card.rank,
                            fill=ink, font=('Helvetica', 10, 'bold'), anchor='center')
        self.cv.create_text(x+sw//2, y+sh//2+9, text=card.suit,
                            fill=ink, font=('Helvetica', 13), anchor='center')

    # ── Main redraw ────────────────────────────────────────────────────────────
    def _redraw(self):
        self.cv.delete('all')
        self._draw_table()
        self._draw_scores()
        self._draw_trick_area()
        self._draw_all_hands()
        if self.show_hints.get() and self.phase == 'playing' and self.trump:
            self._draw_suggestions()
        if self.phase == 'bidding':
            self._draw_bid_panel()
        if self.phase == 'scoring':
            self._draw_score_overlay()

    def _draw_table(self):
        self.cv.create_oval(40, 30, W-40, H-20,
                            fill=BG, outline=C_GREEN, width=3)
        info = [
            (CX,     H-115, 'YOU  (South)',           True),
            (W-80,   CY,    'East  (AI)',              False),
            (CX,     48,    'North  (AI · partner)',   True),
            (80,     CY,    'West  (AI)',              False),
        ]
        for x, y, label, partner in info:
            clr = C_LIME if partner else C_TEXT
            self.cv.create_text(x, y, text=label, fill=clr,
                                font=('Helvetica', 11, 'bold'), anchor='center')

        # Arrow for current player
        arrow_pos = {0: (CX, H-135), 1: (W-155, CY),
                     2: (CX, 68),    3: (155, CY)}
        if self.phase == 'playing' and self.current in arrow_pos:
            ax, ay = arrow_pos[self.current]
            self.cv.create_text(ax, ay, text='▶',
                                fill=C_GOLD, font=('Helvetica', 14))

        # Trump + contract info
        if self.trump:
            ink = C_RED if SUIT_RED[self.trump] else C_BLACK
            self.cv.create_rectangle(8, 8, 230, 68, fill='#0a2218', outline=C_GREEN)
            self.cv.create_text(18, 18, anchor='nw',
                text=f'Trump: {self.trump}',
                fill=ink, font=('Helvetica', 13, 'bold'))
            team = 'You & North' if self.contract_player % 2 == 0 else 'East & West'
            self.cv.create_text(18, 42, anchor='nw',
                text=f'Contract: {self.contract}  by {team}',
                fill=C_GOLD, font=('Helvetica', 10))

    def _draw_scores(self):
        bx, by, bw, bh = W-218, 8, 210, 74
        self.cv.create_rectangle(bx, by, bx+bw, by+bh,
                                 fill='#0a2218', outline=C_GREEN, width=2)
        self.cv.create_text(bx+bw//2, by+13, text='SCORES',
                            fill=C_TEXT, font=('Helvetica', 11, 'bold'))
        self.cv.create_text(bx+bw//2, by+36,
                            text=f'You & North: {self.scores[0]}',
                            fill=C_LIME, font=('Helvetica', 11))
        self.cv.create_text(bx+bw//2, by+58,
                            text=f'East & West: {self.scores[1]}',
                            fill='#fca5a5', font=('Helvetica', 11))

    def _draw_trick_area(self):
        self.cv.create_oval(CX-105, CY-110, CX+105, CY+110,
                            fill='', outline=C_GREEN, width=1, dash=(4, 4))
        for pidx, card in self.trick:
            cx, cy = TRICK_XY[pidx]
            self._draw_card_face(cx - CW//2, cy - CH//2, card)

        if self.trick_pts[0] or self.trick_pts[1]:
            self.cv.create_text(CX, CY - 125,
                text=f'Pts in hand:  You+N={self.trick_pts[0]}  E+W={self.trick_pts[1]}',
                fill=C_GRAY, font=('Helvetica', 10))

    def _draw_all_hands(self):
        # ── Human hand ──
        hand = self.hands[0]
        n = len(hand)
        if n:
            playable = (legal_plays(hand, self.trick, self.trump, 0)
                        if self.phase == 'playing' and self.current == 0 and self.trump
                        else [])
            spread = min(CW + 6, 680 // max(n, 1))
            sx = CX - (spread * (n-1) + CW) // 2
            y  = H - CH - 58
            for i, card in enumerate(hand):
                x   = sx + i * spread
                hl  = card == self.selected
                dim = bool(playable) and card not in playable
                self._draw_card_face(x, y, card, highlight=hl, dim=dim,
                                     tags=(f'hcard_{i}',))

        # ── AI hands (face-down) ──
        self._draw_ai_back(2, 'top')
        self._draw_ai_back(1, 'right')
        self._draw_ai_back(3, 'left')

    def _draw_ai_back(self, pidx: int, pos: str):
        n = len(self.hands[pidx])
        if n == 0:
            return
        if pos == 'top':
            spread = min(CW + 6, 580 // max(n, 1))
            sx = CX - (spread*(n-1) + CW) // 2
            for i in range(n):
                self._draw_card_back(sx + i*spread, 68)
        elif pos == 'right':
            spread = min(CH + 4, 380 // max(n, 1))
            sy = CY - (spread*(n-1) + CH) // 2
            for i in range(n):
                self._draw_card_back(W - CW - 70, sy + i*spread)
        elif pos == 'left':
            spread = min(CH + 4, 380 // max(n, 1))
            sy = CY - (spread*(n-1) + CH) // 2
            for i in range(n):
                self._draw_card_back(70, sy + i*spread)

    def _draw_suggestions(self):
        hint_pos = {1: (W-CW-145, CY-28), 2: (CX-24, 172), 3: (148, CY-28)}
        for pidx in (1, 2, 3):
            if not self.hands[pidx] or not self.trump:
                continue
            card = ai_play(self.hands[pidx], self.trick, self.trump, pidx)
            sx, sy = hint_pos[pidx]
            self.cv.create_rectangle(sx-6, sy-18, sx+56, sy+74,
                                     fill='#111', outline=C_GOLD, width=2)
            self.cv.create_text(sx+24, sy-8, text='plays:',
                                fill=C_GOLD, font=('Helvetica', 8))
            self._draw_mini_card(sx, sy, card)

    # ── Bid panel ──────────────────────────────────────────────────────────────
    def _draw_bid_panel(self):
        px, py, pw, ph = 160, H-200, 730, 155
        self._rrect(px, py, pw, ph, r=12,
                    fill='#0a2218', outline=C_GREEN, width=2)
        self.cv.create_text(px+pw//2, py+18,
                            text='Your bid  –  current contract: '
                                 + (str(self.contract) if self.contract else 'none'),
                            fill=C_TEXT, font=('Helvetica', 12, 'bold'))

        if self.pending_val is None:
            # Row 1: Pass + bid values
            vals = [None, 80, 90, 100, 110, 120, 130, 140, 150, 160]
            for i, v in enumerate(vals):
                bx = px + 12 + i * 71
                by = py + 36
                enabled = v is None or v > self.contract
                fill   = '#1b4332' if enabled else '#333'
                ol     = C_GOLD   if enabled else '#555'
                tag    = f'bidv_{v}'
                self._rrect(bx, by, 64, 32, r=6, fill=fill, outline=ol,
                            width=2, tags=(tag,))
                label = 'Pass' if v is None else str(v)
                self.cv.create_text(bx+32, by+16, text=label,
                                    fill=(C_TEXT if enabled else '#666'),
                                    font=('Helvetica', 10, 'bold'), tags=(tag,))
                if enabled:
                    self.cv.tag_bind(tag, '<Button-1>',
                                     lambda e, val=v: self._on_bid_value(val))
            self.cv.create_text(px+pw//2, py+90,
                                text='Select a bid amount (or Pass)',
                                fill=C_GRAY, font=('Helvetica', 10))
        else:
            # Row 2: choose suit
            self.cv.create_text(px+pw//2, py+50,
                text=f'Bid: {self.pending_val}  –  choose trump suit:',
                fill=C_GOLD, font=('Helvetica', 12, 'bold'))
            for i, s in enumerate(SUITS):
                bx = px + 100 + i * 140
                by = py + 72
                ink = C_RED if SUIT_RED[s] else C_BLACK
                tag = f'bids_{s}'
                self._rrect(bx, by, 110, 52, r=8,
                            fill='#fefae0', outline=C_GOLD, width=2, tags=(tag,))
                self.cv.create_text(bx+55, by+26, text=s,
                                    fill=ink, font=('Helvetica', 24), tags=(tag,))
                self.cv.tag_bind(tag, '<Button-1>',
                                 lambda e, suit=s: self._on_bid_suit(suit))
            # Cancel
            tag = 'bidcancel'
            self._rrect(px+pw-88, py+130, 80, 14, r=4,
                        fill='#444', outline='#888', tags=(tag,))
            self.cv.create_text(px+pw-48, py+137, text='← back',
                                fill=C_GRAY, font=('Helvetica', 9), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>', lambda e: self._cancel_bid_val())

    def _cancel_bid_val(self):
        self.pending_val = None
        self._redraw()

    # ── Score overlay ──────────────────────────────────────────────────────────
    def _draw_score_overlay(self):
        ox, oy, ow, oh = W//2-220, H//2-160, 440, 320
        self._rrect(ox, oy, ow, oh, r=16,
                    fill='#0a2218', outline=C_GOLD, width=3)
        self.cv.create_text(ox+ow//2, oy+28,
                            text='Round over', fill=C_GOLD,
                            font=('Helvetica', 16, 'bold'))

        lines = [
            f"Contract: {self.contract}  by "
            f"{'You & North' if self.contract_player % 2 == 0 else 'East & West'}",
            f"Trump: {self.trump}",
            '',
            f"You & North  card pts: {self.trick_pts[0]}",
            f"East & West  card pts: {self.trick_pts[1]}",
            '',
            f"Running totals:",
            f"You & North: {self.scores[0]}",
            f"East & West: {self.scores[1]}",
        ]
        for i, ln in enumerate(lines):
            self.cv.create_text(ox+ow//2, oy+62 + i*22,
                                text=ln, fill=C_TEXT,
                                font=('Helvetica', 11))

        tag = 'next_round'
        self._rrect(ox+ow//2-70, oy+oh-44, 140, 34, r=8,
                    fill='#991b1b', outline=C_GOLD, width=2, tags=(tag,))
        self.cv.create_text(ox+ow//2, oy+oh-27,
                            text='Next round ▶', fill='white',
                            font=('Helvetica', 12, 'bold'), tags=(tag,))
        self.cv.tag_bind(tag, '<Button-1>', lambda e: self._new_round())

    # ── Game flow ──────────────────────────────────────────────────────────────
    def _new_game(self):
        self.scores  = [0, 0]
        self.dealer  = 0
        self._new_round()

    def _new_round(self):
        deck = fresh_deck()
        random.shuffle(deck)
        self.hands      = [deck[i*8:(i+1)*8] for i in range(4)]
        self.trump      = None
        self.contract   = 0
        self.contract_player = -1
        self.trick      = []
        self.trick_pts  = [0, 0]
        self.tricks_won = [0, 0]
        self.selected    = None
        self.pending_val = None
        self.bid_passes  = 0
        self._bid_count  = 0
        self.current     = (self.dealer + 1) % 4
        self.phase      = 'bidding'
        self.status.config(text='Bidding phase')
        self._redraw()
        if self.current != 0:
            self.root.after(700, self._ai_bid_step)

    def _ai_bid_step(self):
        if self.phase != 'bidding' or self.current == 0:
            return
        val, suit = ai_bid(self.hands[self.current], self.contract)
        self._apply_bid(self.current, val, suit)

    def _apply_bid(self, pidx: int, val: Optional[int], suit: Optional[str]):
        names = ['You', 'East', 'North', 'West']
        if val is None:
            self.bid_passes += 1
            self.status.config(text=f'{names[pidx]} passes  (contract: {self.contract or "–"})')
        else:
            self.bid_passes  = 0
            self.contract    = val
            self.trump       = suit
            self.contract_player = pidx
            self.status.config(text=f'{names[pidx]} bids {val} {suit}')

        self._bid_count += 1

        # Bidding ends after 3 consecutive passes following a bid
        if self.bid_passes >= 3 and self.contract > 0:
            self._start_play()
            return
        # All 4 passed without a bid → redeal
        if self._bid_count >= 4 and self.contract == 0:
            self.dealer = (self.dealer + 1) % 4
            self.status.config(text='No bids – redealing…')
            self._redraw()
            self.root.after(1200, self._new_round)
            return

        self.current = (pidx + 1) % 4
        self._redraw()
        if self.current != 0:
            self.root.after(700, self._ai_bid_step)

    def _on_bid_value(self, val: Optional[int]):
        if val is None:
            self._apply_bid(0, None, None)
        else:
            self.pending_val = val
            self._redraw()

    def _on_bid_suit(self, suit: str):
        val = self.pending_val
        self.pending_val = None
        self._apply_bid(0, val, suit)

    def _start_play(self):
        self.phase   = 'playing'
        self.current = (self.dealer + 1) % 4
        self.trick   = []
        self.status.config(text=f'Playing  –  trump: {self.trump}')
        self._redraw()
        if self.current != 0:
            self.root.after(800, self._ai_play_step)

    def _ai_play_step(self):
        if self.phase != 'playing' or self.current == 0:
            return
        card = ai_play(self.hands[self.current], self.trick,
                       self.trump, self.current)
        self._play_card(self.current, card)

    def _play_card(self, pidx: int, card: Card):
        self.hands[pidx].remove(card)
        self.trick.append((pidx, card))
        if len(self.trick) == 4:
            self._redraw()
            self.root.after(1100, self._finish_trick)
        else:
            self.current = (pidx + 1) % 4
            self._redraw()
            if self.current != 0:
                self.root.after(750, self._ai_play_step)

    def _finish_trick(self):
        winner    = who_wins(self.trick, self.trump)
        team      = winner % 2
        pts       = sum(c.pts(self.trump) for _, c in self.trick)
        self.trick_pts[team]  += pts
        self.tricks_won[team] += 1

        # Last trick bonus
        if not self.hands[0]:
            self.trick_pts[team] += 10

        self.trick   = []
        self.current = winner

        if not self.hands[0]:
            self._finish_round()
        else:
            names = ['You', 'East', 'North', 'West']
            self.status.config(text=f'{names[winner]} wins the trick')
            self._redraw()
            if self.current != 0:
                self.root.after(750, self._ai_play_step)

    def _finish_round(self):
        ct   = self.contract_player % 2   # contracting team
        at   = 1 - ct
        achieved = self.trick_pts[ct]
        if achieved >= self.contract:
            self.scores[ct] += self.trick_pts[ct]
            self.scores[at] += self.trick_pts[at]
        else:
            self.scores[at] += 162

        self.dealer = (self.dealer + 1) % 4
        self.phase  = 'scoring'
        self.status.config(text='Round over – see results')
        self._redraw()

    # ── Click handling ─────────────────────────────────────────────────────────
    def _on_canvas_click(self, event):
        if self.phase != 'playing' or self.current != 0:
            return
        hand = self.hands[0]
        n    = len(hand)
        if n == 0:
            return

        spread = min(CW + 6, 680 // max(n, 1))
        sx = CX - (spread * (n-1) + CW) // 2
        y  = H - CH - 58

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
    app  = BeloteApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
