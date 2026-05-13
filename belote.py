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

TRUMP_ORDER = ['J', '9', 'A', '10', 'K', 'Q', '8', '7']   # index 0 = strongest
PLAIN_ORDER = ['A', '10', 'K', 'Q', 'J', '9', '8', '7']

TRUMP_PTS = {'J': 20, '9': 14, 'A': 11, '10': 10, 'K': 4, 'Q': 3, '8': 0, '7': 0}
PLAIN_PTS = {'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0, '8': 0, '7': 0}

TOTAL_CARD_PTS = 152   # sum of all card points (without dix de der)
WIN_TARGET     = 501   # first team to reach this wins the game

PLAYER_NAMES = ['You', 'East', 'North', 'West']

CW, CH = 68, 96     # card width / height
W,  H  = 1060, 740  # canvas
CX, CY = 510, 340   # table centre

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

# Centre of each player's trick card slot
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
    """Return the subset of hand cards that may legally be played.

    Rules (official):
    1. Must follow led suit if possible.
       - If led suit IS trump: must play higher trump if possible, else any trump.
    2. If cannot follow:
       - Partner is master → free choice (discard or cut).
       - Partner not master (or hasn't played) → must trump if possible,
         must overtrump if possible, else any trump.
    3. If no trump either → free choice.
    """
    if not trick:
        return list(hand)

    led    = trick[0][1].suit
    follow = [c for c in hand if c.suit == led]
    trumps = [c for c in hand if c.suit == trump]
    p_win  = who_wins(trick, trump) == (me + 2) % 4

    if follow:
        if led == trump:
            # Must overtrump if possible
            best = max(c.power(trump, led) for _, c in trick)
            hi   = [c for c in follow if c.power(trump, led) > best]
            return hi if hi else follow
        return follow

    # Cannot follow led suit
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


def ai_bid_round1(hand: List[Card], revealed_suit: str) -> bool:
    """Return True to take (accept revealed card's suit as trump)."""
    return _hand_score(hand, revealed_suit) >= 58


def ai_bid_round2(hand: List[Card], revealed_suit: str) -> Optional[str]:
    """Return a suit to take, or None to pass (second bidding round)."""
    best_suit, best_score = None, 54
    for s in SUITS:
        if s == revealed_suit:
            continue
        sc = _hand_score(hand, s)
        if sc > best_score:
            best_score, best_suit = sc, s
    return best_suit


def ai_play(hand: List[Card], trick: List[Tuple[int, Card]],
            trump: str, me: int) -> Card:
    plays = legal_plays(hand, trick, trump, me)

    if not trick:
        ts = [c for c in plays if c.suit == trump]
        if ts:
            return max(ts, key=lambda c: c.power(trump, trump))
        return max(plays, key=lambda c: c.pts(trump))

    led   = trick[0][1].suit
    p_win = who_wins(trick, trump) == (me + 2) % 4

    if p_win:
        # Partner winning – dump highest-value card to give them points
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
        root.resizable(False, False)
        root.configure(bg=BG_DARK)

        self.show_hints = tk.BooleanVar(value=True)

        # Persistent across rounds
        self.scores     = [0, 0]
        self.litige_pts = 0   # points carried over from a litige round

        # Round state – reset by _new_round
        self.hands:           List[List[Card]] = [[], [], [], []]
        self.trump:           Optional[str]    = None
        self.revealed_card:   Optional[Card]   = None
        self.remaining_deck:  List[Card]       = []
        self.bid_round:       int              = 1   # 1 or 2
        self._bid_count:      int              = 0   # bids/passes in current bid round
        self.contract_player: int              = -1
        self.trick:           List[Tuple[int, Card]] = []
        self.trick_pts:       List[int]        = [0, 0]
        self.tricks_won:      List[int]        = [0, 0]
        self.belote_player:   int              = -1  # player holding K+Q of trump
        self.belote_played:   int              = 0   # how many of K/Q trump played
        self.belote_pts:      List[int]        = [0, 0]  # 20 for team if they have belote
        self.dealer:          int              = 0
        self.current:         int              = 0
        self.selected:        Optional[Card]   = None
        self.phase:           str              = 'idle'
        self.round_info:      dict             = {}

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
        f9  = ('Helvetica', 8,  'bold')
        f8  = ('Helvetica', 8)
        fsz = ('Helvetica', 24) if large else ('Helvetica', 20)
        self.cv.create_text(x+5,   y+4,     text=card.rank,  fill=ink, font=f9, anchor='nw', tags=tags)
        self.cv.create_text(x+5,   y+15,    text=card.suit,  fill=ink, font=f8, anchor='nw', tags=tags)
        self.cv.create_text(x+w//2,y+h//2,  text=card.suit,  fill=ink, font=fsz,anchor='center',tags=tags)
        self.cv.create_text(x+w-5, y+h-4,   text=card.rank,  fill=ink, font=f9, anchor='se', tags=tags)
        self.cv.create_text(x+w-5, y+h-15,  text=card.suit,  fill=ink, font=f8, anchor='se', tags=tags)

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
        if self.phase == 'gameover':
            self._draw_gameover_overlay()

    def _draw_table(self):
        self.cv.create_oval(40, 30, W-40, H-20,
                            fill=BG, outline=C_GREEN, width=3)
        info = [
            (CX,    H-115, 'YOU  (South)',          True),
            (W-80,  CY,    'East  (AI)',             False),
            (CX,    48,    'North  (AI · partner)',  True),
            (80,    CY,    'West  (AI)',             False),
        ]
        for x, y, label, partner in info:
            clr = C_LIME if partner else C_TEXT
            self.cv.create_text(x, y, text=label, fill=clr,
                                font=('Helvetica', 11, 'bold'), anchor='center')

        # Current-player arrow
        arrow_pos = {0: (CX, H-135), 1: (W-155, CY), 2: (CX, 68), 3: (155, CY)}
        if self.phase == 'playing' and self.current in arrow_pos:
            ax, ay = arrow_pos[self.current]
            self.cv.create_text(ax, ay, text='▶',
                                fill=C_GOLD, font=('Helvetica', 14))

        # Trump + contract info
        if self.trump:
            ink  = C_RED if SUIT_RED[self.trump] else C_BLACK
            team = 'You & North' if self.contract_player % 2 == 0 else 'East & West'
            self.cv.create_rectangle(8, 8, 240, 68, fill='#0a2218', outline=C_GREEN)
            self.cv.create_text(18, 18, anchor='nw',
                text=f'Atout / Trump: {self.trump}',
                fill=ink, font=('Helvetica', 13, 'bold'))
            self.cv.create_text(18, 42, anchor='nw',
                text=f'Preneurs / Takers: {team}',
                fill=C_GOLD, font=('Helvetica', 10))

        # Belote announcement badge
        if self.belote_player >= 0 and self.belote_played > 0:
            msg = 'Rebelote!' if self.belote_played >= 2 else 'Belote!'
            team_name = ('You & North' if self.belote_player % 2 == 0
                         else 'East & West')
            self.cv.create_text(18, 68, anchor='nw',
                text=f'{msg}  ({team_name})',
                fill='#ff9f40', font=('Helvetica', 10, 'bold'))

        # Litige indicator
        if self.litige_pts > 0:
            self.cv.create_text(18, 86, anchor='nw',
                text=f'Litige: {self.litige_pts} pts in play',
                fill='#ffa0a0', font=('Helvetica', 10, 'italic'))

    def _draw_scores(self):
        bx, by, bw, bh = W-218, 8, 210, 74
        self.cv.create_rectangle(bx, by, bx+bw, by+bh,
                                 fill='#0a2218', outline=C_GREEN, width=2)
        self.cv.create_text(bx+bw//2, by+13, text='SCORES  (first to 501)',
                            fill=C_TEXT, font=('Helvetica', 10, 'bold'))
        self.cv.create_text(bx+bw//2, by+36,
                            text=f'You & North: {self.scores[0]}',
                            fill=C_LIME, font=('Helvetica', 11))
        self.cv.create_text(bx+bw//2, by+58,
                            text=f'East & West: {self.scores[1]}',
                            fill='#fca5a5', font=('Helvetica', 11))

    def _draw_trick_area(self):
        self.cv.create_oval(CX-105, CY-110, CX+105, CY+110,
                            fill='', outline=C_GREEN, width=1, dash=(4, 4))

        # Revealed card (shown face-up in centre during bidding or before play starts)
        if self.revealed_card and self.phase == 'bidding':
            rx = CX - (CW+10)//2
            ry = CY - (CH+14)//2
            self.cv.create_text(CX, ry - 14, text='Carte retournée',
                                fill=C_GOLD, font=('Helvetica', 9, 'italic'))
            self._draw_card_face(rx, ry, self.revealed_card, large=True)

        for pidx, card in self.trick:
            cx, cy = TRICK_XY[pidx]
            self._draw_card_face(cx - CW//2, cy - CH//2, card)

        if self.trick_pts[0] or self.trick_pts[1]:
            self.cv.create_text(
                CX, CY - 125,
                text=(f'Pts in hand:  '
                      f'You+N={self.trick_pts[0]}  '
                      f'E+W={self.trick_pts[1]}'),
                fill=C_GRAY, font=('Helvetica', 10))

    def _draw_all_hands(self):
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
        px, py, pw, ph = 200, H - 185, 660, 140
        self._rrect(px, py, pw, ph, r=12,
                    fill='#0a2218', outline=C_GREEN, width=2)

        if self.bid_round == 1:
            suit = self.revealed_card.suit
            ink  = C_RED if SUIT_RED[suit] else C_BLACK
            self.cv.create_text(px+pw//2, py+18,
                text=f'Tour de prise  –  Round 1 of 2  '
                     f'(accept {suit} as trump or pass)',
                fill=C_TEXT, font=('Helvetica', 11, 'bold'))

            # Take button
            tag = 'bid_take'
            self._rrect(px+120, py+50, 160, 56, r=8,
                        fill='#1b4332', outline=C_GOLD, width=2, tags=(tag,))
            self.cv.create_text(px+200, py+78,
                text=f'Take  {suit}', fill=C_TEXT,
                font=('Helvetica', 14, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>',
                             lambda e: self._on_bid_take(None))

            # Pass button
            tag = 'bid_pass'
            self._rrect(px+360, py+50, 160, 56, r=8,
                        fill='#222', outline='#666', width=2, tags=(tag,))
            self.cv.create_text(px+440, py+78,
                text='Pass', fill=C_GRAY,
                font=('Helvetica', 14, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>',
                             lambda e: self._on_bid_pass())

        else:  # round 2
            revealed = self.revealed_card.suit
            other    = [s for s in SUITS if s != revealed]
            self.cv.create_text(px+pw//2, py+18,
                text=f'Tour de prise  –  Round 2  '
                     f'(choose trump, not {revealed})',
                fill=C_TEXT, font=('Helvetica', 11, 'bold'))
            for i, s in enumerate(other):
                bx  = px + 30 + i * 155
                ink = C_RED if SUIT_RED[s] else C_BLACK
                tag = f'bid_suit_{s}'
                self._rrect(bx, py+45, 130, 56, r=8,
                            fill='#fefae0', outline=C_GOLD, width=2, tags=(tag,))
                self.cv.create_text(bx+65, py+73,
                    text=s, fill=ink,
                    font=('Helvetica', 26), tags=(tag,))
                self.cv.tag_bind(tag, '<Button-1>',
                                 lambda e, suit=s: self._on_bid_take(suit))

            # Pass button
            tag = 'bid_pass2'
            self._rrect(px+500, py+45, 130, 56, r=8,
                        fill='#222', outline='#666', width=2, tags=(tag,))
            self.cv.create_text(px+565, py+73,
                text='Pass', fill=C_GRAY,
                font=('Helvetica', 14, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>',
                             lambda e: self._on_bid_pass())

    # ── Score overlay ──────────────────────────────────────────────────────────
    def _draw_score_overlay(self):
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
        taker_name = team_names[ct]
        def_name   = team_names[at]

        ox, oy, ow, oh = W//2-240, H//2-200, 480, 400
        self._rrect(ox, oy, ow, oh, r=16, fill='#0a2218', outline=C_GOLD, width=3)

        self.cv.create_text(ox+ow//2, oy+24,
                            text='Round over', fill=C_GOLD,
                            font=('Helvetica', 15, 'bold'))
        self.cv.create_text(ox+ow//2, oy+52,
                            text=res_text, fill=res_color,
                            font=('Helvetica', 13, 'bold'))

        trump_ink = C_RED if self.trump and SUIT_RED[self.trump] else C_BLACK
        lines = [
            (f"Trump: {self.trump}  |  Takers: {taker_name}", trump_ink),
            ('', C_TEXT),
            (f"{taker_name}  tricks pts: {ri.get('taker_trick_pts', 0)}", C_TEXT),
            (f"{def_name}  tricks pts: {ri.get('def_trick_pts', 0)}", C_TEXT),
        ]
        if ri.get('belote_team') is not None:
            bteam = team_names[ri['belote_team']]
            lines.append((f"Belote: {bteam} +20 pts  (imprenable)", '#ff9f40'))
        lines += [
            ('', C_TEXT),
            (f"{taker_name}  total: {ri.get('taker_pts', 0)}", C_TEXT),
            (f"{def_name}  total: {ri.get('def_pts', 0)}", C_TEXT),
        ]
        if result == 'litige':
            lines.append((f"Litige: {ri.get('litige_after', 0)} pts carried over", '#ffa0a0'))

        for i, (ln, clr) in enumerate(lines):
            self.cv.create_text(ox+ow//2, oy+80 + i*22,
                                text=ln, fill=clr, font=('Helvetica', 11))

        # Running scores
        sep_y = oy + 80 + len(lines) * 22 + 6
        self.cv.create_line(ox+30, sep_y, ox+ow-30, sep_y,
                            fill='#2d6a4f', width=1)
        self.cv.create_text(ox+ow//2, sep_y + 14,
                            text='Running scores:', fill=C_GRAY,
                            font=('Helvetica', 10))
        self.cv.create_text(ox+ow//2, sep_y + 32,
                            text=f'You & North: {self.scores[0]}   '
                                 f'East & West: {self.scores[1]}',
                            fill=C_TEXT, font=('Helvetica', 11, 'bold'))

        btn_y = oy + oh - 44
        tag   = 'next_round'
        self._rrect(ox+ow//2-70, btn_y, 140, 34, r=8,
                    fill='#991b1b', outline=C_GOLD, width=2, tags=(tag,))
        self.cv.create_text(ox+ow//2, btn_y+17,
                            text='Next round ▶', fill='white',
                            font=('Helvetica', 12, 'bold'), tags=(tag,))
        self.cv.tag_bind(tag, '<Button-1>', lambda e: self._new_round())

    def _draw_gameover_overlay(self):
        winner = 0 if self.scores[0] > self.scores[1] else 1
        team   = ['You & North', 'East & West'][winner]
        color  = C_LIME if winner == 0 else '#fca5a5'

        ox, oy, ow, oh = W//2-220, H//2-140, 440, 280
        self._rrect(ox, oy, ow, oh, r=16, fill='#0a2218', outline=C_GOLD, width=3)
        self.cv.create_text(ox+ow//2, oy+36,
                            text='Game Over', fill=C_GOLD,
                            font=('Helvetica', 18, 'bold'))
        self.cv.create_text(ox+ow//2, oy+80,
                            text=f'🏆  {team} win!', fill=color,
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
        self.scores     = [0, 0]
        self.litige_pts = 0
        self.dealer     = 0
        self._new_round()

    def _new_round(self):
        """Deal 5 cards each, reveal one card, start bidding."""
        deck = fresh_deck()
        random.shuffle(deck)

        start = (self.dealer + 1) % 4
        # Deal 5 cards each starting from player to dealer's right
        for i in range(4):
            pidx = (start + i) % 4
            self.hands[pidx] = deck[i*5 : i*5+5]

        self.revealed_card  = deck[20]       # the turned-up card
        self.remaining_deck = deck[21:]      # 11 cards left to deal after take

        self.trump           = None
        self.contract_player = -1
        self.trick           = []
        self.trick_pts       = [0, 0]
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
        """After take: give taker the revealed card + 2 more; give others 3 each."""
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
        """After trump is set, find which player (if any) holds K+Q of trump."""
        self.belote_player = -1
        self.belote_played = 0
        for pidx in range(4):
            has_k = any(c.suit == self.trump and c.rank == 'K'
                        for c in self.hands[pidx])
            has_q = any(c.suit == self.trump and c.rank == 'Q'
                        for c in self.hands[pidx])
            if has_k and has_q:
                self.belote_player = pidx
                break

    # ── Bidding flow ───────────────────────────────────────────────────────────
    def _ai_bid_step(self):
        if self.phase != 'bidding' or self.current == 0:
            return
        pidx = self.current
        if self.bid_round == 1:
            if ai_bid_round1(self.hands[pidx], self.revealed_card.suit):
                self._apply_take(pidx, None)   # None = use revealed suit
            else:
                self._apply_pass(pidx)
        else:
            suit = ai_bid_round2(self.hands[pidx], self.revealed_card.suit)
            if suit:
                self._apply_take(pidx, suit)
            else:
                self._apply_pass(pidx)

    def _apply_take(self, pidx: int, suit: Optional[str]):
        """Player pidx takes. suit=None means revealed card's suit (round 1)."""
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
                # Move to round 2
                self.bid_round  = 2
                self._bid_count = 0
                self.current    = (self.dealer + 1) % 4
                self.status.config(text='Bidding phase – round 2')
                self._redraw()
                if self.current != 0:
                    self.root.after(700, self._ai_bid_step)
            else:
                # All passed in round 2 → redeal
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
        """Human takes (suit=None → accept revealed, else chosen suit)."""
        self._apply_take(0, suit)

    def _on_bid_pass(self):
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
                       self.trump, self.current)
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
        """Announce Belote/Rebelote when the holder plays K or Q of trump."""
        if pidx != self.belote_player:
            return
        if card.suit != self.trump or card.rank not in ('K', 'Q'):
            return
        self.belote_played += 1
        team = pidx % 2
        self.belote_pts[team] = 20   # imprenable – always scored
        word = 'Rebelote!' if self.belote_played >= 2 else 'Belote!'
        self.status.config(text=f'{word}  ({PLAYER_NAMES[pidx]})')

    def _finish_trick(self):
        winner = who_wins(self.trick, self.trump)
        team   = winner % 2
        pts    = sum(c.pts(self.trump) for _, c in self.trick)
        self.trick_pts[team]  += pts
        self.tricks_won[team] += 1

        is_last = not self.hands[0]   # all cards played after this trick
        if is_last:
            # Dix de der: +10 normally, +100 if capot
            capot = (self.tricks_won[1 - team] == 0)
            self.trick_pts[team] += 100 if capot else 10

        self.trick   = []
        self.current = winner

        if is_last:
            self._finish_round()
        else:
            self.status.config(text=f'{PLAYER_NAMES[winner]} wins the trick')
            self._redraw()
            if self.current != 0:
                self.root.after(750, self._ai_play_step)

    def _finish_round(self):
        """Compute scores according to official Belote rules."""
        ct = self.contract_player % 2   # contracting team
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
            # Capot: one team won all 8 tricks
            w, l    = (ct, at) if all_to_ct else (at, ct)
            result  = 'capot'
            # Winner gets 252 + their belote; loser keeps their belote (imprenable)
            self.scores[w] += taker_pts + def_pts - self.belote_pts[l] + self.litige_pts
            self.scores[l] += self.belote_pts[l]
            self.litige_pts = 0

        elif taker_pts > def_pts:
            # Contract fulfilled
            result = 'success'
            self.scores[ct] += taker_pts + self.litige_pts
            self.scores[at] += def_pts
            self.litige_pts = 0

        elif taker_pts == def_pts:
            # Litige (81-81)
            result = 'litige'
            self.scores[at] += def_pts
            self.litige_pts += taker_pts

        else:
            # Chute: contract failed
            result = 'chute'
            self.scores[ct] += self.belote_pts[ct]   # imprenable
            self.scores[at] += 162 + self.belote_pts[at] + self.litige_pts
            self.litige_pts = 0

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

        self.dealer = (self.dealer + 1) % 4
        self.status.config(text='Round over – see results')

        # Check for game over
        if max(self.scores) >= WIN_TARGET:
            self.phase = 'gameover'
        else:
            self.phase = 'scoring'
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
    BeloteApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
