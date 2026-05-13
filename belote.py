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

# Bidding hierarchy for round 2 (lowest → highest)
BID_MODES = ['♣', '♦', '♠', '♥', 'SA', 'TA']
BID_RANK  = {m: i for i, m in enumerate(BID_MODES)}

WIN_TARGET = 501
SCORE_W    = 260   # width of the right-side score/history panel

PLAYER_NAMES = ['You', 'East', 'North', 'West']

# Card dimensions (fixed regardless of window size)
CW, CH = 88, 124
SIDE_CARD_MIN_Y = 115  # keep East/West cards below the top-left info box

# Default window size
DEFAULT_W, DEFAULT_H = 1260, 860

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
        if trump == 'SA':
            return PLAIN_PTS[self.rank]
        if trump == 'TA':
            return TRUMP_PTS[self.rank]
        return TRUMP_PTS[self.rank] if self.suit == trump else PLAIN_PTS[self.rank]

    def power(self, trump: str, led: str) -> int:
        if trump == 'SA':
            if self.suit == led:
                return 100 + len(PLAIN_ORDER) - PLAIN_ORDER.index(self.rank)
            return 0
        if trump == 'TA':
            if self.suit == led:
                return 200 + len(TRUMP_ORDER) - TRUMP_ORDER.index(self.rank)
            return 0
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

    # SA/TA: no trump suit, just follow led suit (no overtrumping requirement)
    if trump in ('SA', 'TA'):
        if follow:
            if trump == 'TA':
                best = max(c.power(trump, led) for _, c in trick)
                hi   = [c for c in follow if c.power(trump, led) > best]
                return hi if hi else follow
            return follow
        return list(hand)

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
def _bid_score_normal(hand: List[Card], suit: str,
                      extra_card: Optional[Card] = None) -> tuple:
    """Score a normal-trump hand for bidding. Returns (score, metadata dict).

    extra_card: the revealed card (counts toward trump if same suit, added to hand).
    Score components:
      - Trump pts: J=20, 9=14, A=11, 10=10, K=4, Q=3
      - Trump length bonus: 4→+8, 5→+18, 6→+25, 7+→+30
      - Side aces: +8 each (guaranteed points + hand control)
      - Isolated 10s (10 without matching A): -5 each (vulnerable to opponent's A)
    """
    trump_cards = [c for c in hand if c.suit == suit]
    if extra_card and extra_card.suit == suit:
        trump_cards = trump_cards + [extra_card]

    has_j   = any(c.rank == 'J' for c in trump_cards)
    has_9   = any(c.rank == '9' for c in trump_cards)
    n_trump = len(trump_cards)
    t_pts   = sum(TRUMP_PTS[c.rank] for c in trump_cards)

    side_aces = sum(1 for c in hand if c.rank == 'A' and c.suit != suit)
    iso_tens  = sum(
        1 for c in hand if c.rank == '10' and c.suit != suit
        and not any(o.suit == c.suit and o.rank == 'A' for o in hand)
    )

    len_bonus = (0, 0, 0, 0, 8, 18, 25, 30)[min(n_trump, 7)]
    score = t_pts + len_bonus + side_aces * 8 - iso_tens * 5

    return score, {'has_j': has_j, 'has_9': has_9, 'n_trump': n_trump,
                   'side_aces': side_aces}


def _is_master(card: Card, trump: str, played: set) -> bool:
    """True if no unplayed card can beat this card in its suit."""
    if trump == 'TA':
        order = TRUMP_ORDER
    elif card.suit == trump:
        order = TRUMP_ORDER
    else:
        order = PLAIN_ORDER
    idx = order.index(card.rank)
    return all(Card(card.suit, r) in played for r in order[:idx])


def ai_bid_round1(hand: List[Card], revealed_card: Card,
                  passes_before: int = 0) -> bool:
    """Return True if AI should take the contract in round 1.

    passes_before: number of players who passed before this AI (0–3).
    Strategy: J is required except in exceptional cases; later position = lower bar.
    """
    sc, m = _bid_score_normal(hand, revealed_card.suit, revealed_card)

    if not m['has_j']:
        # Exceptional cases without J
        if m['n_trump'] >= 5:        # long suit compensates
            return True
        if m['has_9'] and m['n_trump'] >= 4 and passes_before >= 2:
            return True
        if m['has_9'] and m['n_trump'] >= 3 and m['side_aces'] >= 2 and passes_before >= 3:
            return True
        return False

    # With J: position-adjusted threshold (earlier position = higher bar)
    threshold = (42, 38, 34, 28)[min(passes_before, 3)]
    return sc >= threshold


def ai_bid_round2(hand: List[Card], revealed_suit: str,
                  min_bid_rank: int = 0,
                  passes_before: int = 0) -> Optional[str]:
    """Return best bid mode or None to pass in round 2.

    min_bid_rank: only consider bids ranked strictly above this.
    passes_before: players who have already acted in round 2 (0–3).
    Round 2 has a higher bar: the revealed card goes to the taker's opponent pile.
    """
    best_mode, best_score = None, 47  # higher floor than round 1 (min to bid: 48)

    for s in SUITS:
        if s == revealed_suit or BID_RANK[s] <= min_bid_rank:
            continue

        sc, m = _bid_score_normal(hand, s)

        if not m['has_j']:
            # Allow without J only for very long or 9-heavy suits
            if m['n_trump'] >= 5:
                sc -= 5
            elif m['has_9'] and m['n_trump'] >= 4:
                sc -= 12
            else:
                continue  # don't bid without J in round 2

        sc += passes_before * 3  # later position = slightly lower risk

        if sc > best_score:
            best_score, best_mode = sc, s

    # SA: Aces and 10s heavy
    if BID_RANK['SA'] > min_bid_rank:
        sa_sc = sum(PLAIN_PTS[c.rank] for c in hand)
        aces  = sum(1 for c in hand if c.rank == 'A')
        tens  = sum(1 for c in hand if c.rank == '10')
        if (aces >= 3 or tens >= 3 or (aces >= 2 and tens >= 2)) and sa_sc >= 55:
            sa_adj = sa_sc + passes_before * 3
            if sa_adj > best_score:
                best_score, best_mode = sa_adj, 'SA'

    # TA: Jacks and 9s heavy
    if BID_RANK['TA'] > min_bid_rank:
        jacks = sum(1 for c in hand if c.rank == 'J')
        nines = sum(1 for c in hand if c.rank == '9')
        ta_sc = int(jacks * 25 + nines * 15 + sum(TRUMP_PTS[c.rank] for c in hand) * 0.3)
        if (jacks >= 3 or nines >= 3 or (jacks >= 2 and nines >= 2)) and ta_sc >= 55:
            ta_adj = ta_sc + passes_before * 3
            if ta_adj > best_score:
                best_score, best_mode = ta_adj, 'TA'

    return best_mode


def _trick_pts(trick: List[Tuple[int, Card]], trump: str) -> int:
    """Total point value currently in a trick."""
    return sum(c.pts(trump) for _, c in trick)


def ai_play(hand: List[Card], trick: List[Tuple[int, Card]],
            trump: str, me: int,
            played_cards: Optional[List[Card]] = None,
            contract_player: int = -1) -> Card:
    """Belote AI – playing phase."""
    plays   = legal_plays(hand, trick, trump, me)
    played  = set(played_cards) if played_cards else set()
    partner = (me + 2) % 4
    partner_has_contract = (contract_player >= 0
                            and contract_player % 2 == me % 2
                            and contract_player != me)

    # ── Leading ──────────────────────────────────────────────────────────────
    if not trick:
        # 1. Lead a master card (guaranteed win) — prefer highest value
        masters = [c for c in plays if _is_master(c, trump, played)]
        if masters:
            return max(masters, key=lambda c: c.pts(trump))

        ts = [c for c in plays if c.suit == trump]
        # 2. Partner or self took contract → lead trump to exhaust opponents
        if (partner_has_contract or contract_player == me) and ts:
            return max(ts, key=lambda c: c.power(trump, trump))

        # 3. Default: lead highest-value card, but don't lead trump 9 while J is live
        trump_j_out = any(c.suit == trump and c.rank == 'J' for c in played)
        safe = [c for c in plays
                if not (c.suit == trump and c.rank == '9' and not trump_j_out)]
        return max((safe or plays), key=lambda c: c.pts(trump))

    # ── Following ─────────────────────────────────────────────────────────────
    led   = trick[0][1].suit
    p_win = who_wins(trick, trump) == partner
    tv    = _trick_pts(trick, trump)   # points already in the trick

    # Partner is currently winning this trick
    if p_win:
        if tv >= 10:
            # Valuable trick → pile on our best card to maximise haul
            return max(plays, key=lambda c: c.pts(trump))
        else:
            # Cheap trick → discard our least valuable card; save good ones
            return min(plays, key=lambda c: c.pts(trump))

    # Opponent is currently winning — try to take the trick
    best = max(c.power(trump, led) for _, c in trick)
    win  = [c for c in plays if c.power(trump, led) > best]

    if win:
        if tv >= 10:
            # Worth taking → use the minimum force needed (save stronger cards)
            return min(win, key=lambda c: c.power(trump, led))
        else:
            # Cheap trick → prefer a non-trump winner to spare our trumps
            non_trump_win = [c for c in win if c.suit != trump]
            if non_trump_win:
                return min(non_trump_win, key=lambda c: c.power(trump, led))
            # Only trump can win; legal rules already force us to cut → minimise waste
            return min(win, key=lambda c: c.power(trump, led))

    # Can't win this trick → smart discard
    # Prefer to shed from suits where we hold no future winners, to protect masters
    master_suits = {c.suit for c in hand if _is_master(c, trump, played)}
    discard_pool = [c for c in plays if c.suit not in master_suits] or plays
    return min(discard_pool, key=lambda c: c.pts(trump))


# ── Annonces ───────────────────────────────────────────────────────────────────
def detect_annonces(hand: List[Card]) -> List[dict]:
    """Return all declarable annonces in hand (carrés and suites ≥ 3)."""
    from collections import Counter
    ann = []
    counts = Counter(c.rank for c in hand)
    for rank, cnt in counts.items():
        if cnt == 4:
            pts = 200 if rank == 'J' else 150 if rank == '9' else 100
            ann.append({'type': 'carre', 'rank': rank, 'pts': pts, 'suit': None})
    for suit in SUITS:
        idxs = sorted(set(RANKS.index(c.rank) for c in hand if c.suit == suit))
        i = 0
        while i < len(idxs):
            j = i
            while j + 1 < len(idxs) and idxs[j + 1] == idxs[j] + 1:
                j += 1
            run = j - i + 1
            if run >= 3:
                pts = 100 if run >= 5 else 50 if run == 4 else 20
                ann.append({'type': 'suite', 'suit': suit, 'len': run,
                            'top': RANKS[idxs[j]], 'pts': pts})
            i = j + 1
    return ann


def _ann_sort_key(ann: dict, trump: str) -> tuple:
    trump_b = 1 if ann.get('suit') == trump else 0
    if ann['type'] == 'carre':
        rank_b = 10 if ann['rank'] == 'J' else 9 if ann['rank'] == '9' else 8
    else:
        rank_b = RANKS.index(ann['top'])
    return (ann['pts'], trump_b, rank_b)


def ann_winner_team(all_ann: List[List[dict]], trump: str) -> int:
    """Return 0 (South+North wins), 1 (East+West wins), or -1 (void/none)."""
    team = [[*all_ann[0], *all_ann[2]], [*all_ann[1], *all_ann[3]]]
    bests = [max(t, key=lambda a: _ann_sort_key(a, trump)) if t else None
             for t in team]
    if not bests[0] and not bests[1]:
        return -1
    if not bests[0]:
        return 1
    if not bests[1]:
        return 0
    k0 = _ann_sort_key(bests[0], trump)
    k1 = _ann_sort_key(bests[1], trump)
    if k0 > k1:
        return 0
    if k1 > k0:
        return 1
    return -1


# ── Mode helpers ───────────────────────────────────────────────────────────────
def _mode_label(trump: Optional[str]) -> str:
    if trump == 'SA':
        return 'Sans Atout'
    if trump == 'TA':
        return 'Tout Atout'
    return f'Atout {trump}' if trump else '?'


def _score_threshold(trump: Optional[str]) -> int:
    """Minimum trick points for the taking team to succeed."""
    if trump == 'SA':
        return 66   # >half of 130 total (120 card pts + 10 der)
    if trump == 'TA':
        return 130  # >half of 258 total (248 card pts + 10 der)
    return 82       # standard: >half of 162


def _full_trick_pts(trump: Optional[str]) -> int:
    """Total card trick points awarded to defenders on chute (no 10-de-der)."""
    if trump == 'SA':
        return 120
    if trump == 'TA':
        return 248
    return 162


# ── Application ────────────────────────────────────────────────────────────────
class BeloteApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Belote")
        root.minsize(960, 680)
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

        # Round 2 competitive bidding state
        self.best_bid_rank:   int           = 0
        self.best_bid_player: int           = -1
        self.best_bid_mode:   Optional[str] = None

        # Per-player bid actions shown during auction (player_idx → label str)
        self.bid_actions:     dict          = {}

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
        self.annonces:           List[List[dict]]       = [[], [], [], []]
        self.annonce_winner_team: int                   = -1
        self.annonce_pts:        List[int]              = [0, 0]
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
                       font=('Helvetica', 15)).pack(side='left', padx=18, pady=10)

        self.status = tk.Label(bar, text='', bg=BG_DARK, fg=C_GOLD,
                               font=('Helvetica', 15, 'bold'))
        self.status.pack(side='left', padx=18)

        tk.Button(bar, text='New Game', command=self._new_game,
                  bg='#991b1b', fg='white', relief='flat',
                  font=('Helvetica', 14, 'bold'), padx=12, pady=4,
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
        f9  = ('Helvetica', 11, 'bold')
        f8  = ('Helvetica', 11)
        fsz = ('Helvetica', 28) if large else ('Helvetica', 24)
        self.cv.create_text(x+5,   y+4,    text=card.rank, fill=ink, font=f9, anchor='nw', tags=tags)
        self.cv.create_text(x+5,   y+15,   text=card.suit, fill=ink, font=f8, anchor='nw', tags=tags)
        self.cv.create_text(x+w//2,y+h//2, text=card.suit, fill=ink, font=fsz,anchor='center',tags=tags)
        self.cv.create_text(x+w-5, y+h-4,  text=card.rank, fill=ink, font=f9, anchor='se', tags=tags)
        self.cv.create_text(x+w-5, y+h-15, text=card.suit, fill=ink, font=f8, anchor='se', tags=tags)

    def _draw_mini_card(self, x, y, card: Card):
        sw, sh = 58, 80
        self._rrect(x, y, sw, sh, r=5, fill='#fffde8', outline=C_GOLD, width=2)
        ink = C_RED if SUIT_RED[card.suit] else C_BLACK
        self.cv.create_text(x+sw//2, y+sh//2-9, text=card.rank,
                            fill=ink, font=('Helvetica', 13, 'bold'), anchor='center')
        self.cv.create_text(x+sw//2, y+sh//2+9, text=card.suit,
                            fill=ink, font=('Helvetica', 16), anchor='center')

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
        if self.phase == 'announcing':
            self._draw_annonce_panel()
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
            (CX,              50,    'North  (AI · partner)',  True),
        ]
        for x, y, label, partner in info:
            clr = C_LIME if partner else C_TEXT
            self.cv.create_text(x, y, text=label, fill=clr,
                                font=('Helvetica', 14, 'bold'), anchor='center')

        arrow_pos = {
            0: (CX,                   H-mg-20),
            1: (W-SCORE_W-mg//2-50,  CY),
            2: (CX,                   70),
            3: (mg+70,                CY),
        }
        if self.phase == 'playing' and self.current in arrow_pos:
            ax, ay = arrow_pos[self.current]
            self.cv.create_text(ax, ay, text='▶',
                                fill=C_GOLD, font=('Helvetica', 17))

        if self.trump:
            team = 'You & North' if self.contract_player % 2 == 0 else 'East & West'
            self.cv.create_rectangle(8, 8, 240, 78, fill='#0a2218', outline=C_GREEN)
            if self.trump in ('SA', 'TA'):
                mode_name = 'Sans Atout' if self.trump == 'SA' else 'Tout Atout'
                self.cv.create_text(18, 18, anchor='nw',
                    text=mode_name,
                    fill=C_TEXT, font=('Helvetica', 16, 'bold'))
                self.cv.create_text(18, 40, anchor='nw',
                    text='Pas d\'atout',
                    fill=C_GRAY, font=('Helvetica', 12, 'italic'))
            else:
                ink = C_RED if SUIT_RED[self.trump] else C_TEXT
                self.cv.create_text(18, 18, anchor='nw',
                    text=f'Atout: {self.trump}',
                    fill=ink, font=('Helvetica', 16, 'bold'))
                self.cv.create_text(18, 40, anchor='nw',
                    text='Normale',
                    fill=C_GRAY, font=('Helvetica', 12, 'italic'))
            self.cv.create_text(18, 57, anchor='nw',
                text=f'Preneurs: {team}',
                fill=C_GOLD, font=('Helvetica', 13))

        if self.belote_player >= 0 and self.belote_played > 0:
            msg       = 'Rebelote!' if self.belote_played >= 2 else 'Belote!'
            team_name = 'You & North' if self.belote_player % 2 == 0 else 'East & West'
            self.cv.create_text(18, 82, anchor='nw',
                text=f'{msg}  ({team_name})',
                fill='#ff9f40', font=('Helvetica', 13, 'bold'))

        if self.litige_pts > 0:
            self.cv.create_text(18, 86, anchor='nw',
                text=f'Litige: {self.litige_pts} pts in play',
                fill='#ffa0a0', font=('Helvetica', 13, 'italic'))

    def _draw_scores(self):
        W, H = self.W, self.H
        px, py = W - SCORE_W, 5
        ph = H - 10

        self.cv.create_rectangle(px, py, px + SCORE_W, py + ph,
                                 fill='#0a2218', outline=C_GREEN, width=2)

        # ── Header ──────────────────────────────────────────────────────────
        self.cv.create_text(px + SCORE_W // 2, py + 14,
                            text=f'FIRST TO {WIN_TARGET}',
                            fill=C_TEXT, font=('Helvetica', 13, 'bold'))

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
                                fill=color, font=('Helvetica', 12, 'bold'), anchor='nw')
            self.cv.create_text(px + SCORE_W - 8, y, text=str(score),
                                fill=color, font=('Helvetica', 13, 'bold'), anchor='ne')
            y += 20
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
                            fill=C_GRAY, font=('Helvetica', 11))
        y += 18

        # ── Separator ───────────────────────────────────────────────────────
        self.cv.create_line(px + 8, y, px + SCORE_W - 8, y,
                            fill=C_GREEN, width=1)
        y += 6

        # ── Round history header ─────────────────────────────────────────────
        self.cv.create_text(px + SCORE_W // 2, y + 7,
                            text=f'Round History  (#{self.round_num})',
                            fill=C_GRAY, font=('Helvetica', 12, 'bold'))
        y += 20

        # ── Per-round rows (newest first) ────────────────────────────────────
        RESULT_ICON = {
            'success': ('✓', C_LIME),
            'chute':   ('✗', '#ff6b6b'),
            'litige':  ('⚖', C_GOLD),
            'capot':   ('★', '#ff9f40'),
        }
        TEAM_SHORT = ['Y+N', 'E+W']
        row_h      = 34
        ORDER_H    = 210  # height reserved at bottom for card order section

        for rnd in reversed(self.round_history):
            if y + row_h > py + ph - ORDER_H - 4:
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
                                fill=C_GRAY, font=('Helvetica', 11), anchor='nw')
            # Icon
            self.cv.create_text(px + 34, y + 5,
                                text=icon,
                                fill=icon_color, font=('Helvetica', 12, 'bold'), anchor='nw')
            # Taker label
            self.cv.create_text(px + 50, y + 5,
                                text=ct_short,
                                fill=icon_color, font=('Helvetica', 11, 'bold'), anchor='nw')
            # Points for this round
            self.cv.create_text(px + SCORE_W - 8, y + 5,
                                text=f'{rnd["taker_pts"]}–{rnd["def_pts"]}',
                                fill=C_DIM, font=('Helvetica', 11), anchor='ne')
            # Running total
            self.cv.create_text(px + 12, y + 19,
                                text=f'YN:{s0}  EW:{s1}',
                                fill=C_DIM, font=('Helvetica', 11), anchor='nw')
            y += row_h

        # ── Card order reference (bottom of panel) ───────────────────────────
        oy = py + ph - ORDER_H
        self.cv.create_line(px + 8, oy, px + SCORE_W - 8, oy,
                            fill=C_GREEN, width=1)
        cx = px + SCORE_W // 2
        self.cv.create_text(cx, oy + 10,
                            text='Order  (strongest → weakest)',
                            fill=C_GRAY, font=('Helvetica', 11, 'italic'), anchor='center')

        # Two columns: left = Atout/TA, right = SA/Couleur
        col_l = px + 10
        col_r = px + SCORE_W // 2 + 4
        row_h = 20
        header_y = oy + 26

        self.cv.create_text(col_l, header_y, anchor='nw',
                            text='Atout / TA', fill='#aaddff',
                            font=('Helvetica', 12, 'bold'))
        self.cv.create_text(col_r, header_y, anchor='nw',
                            text='SA / Couleur', fill=C_DIM,
                            font=('Helvetica', 12, 'bold'))

        trump_pts_map = {'J': 20, '9': 14, 'A': 11, '10': 10,
                         'K': 4,  'Q': 3,  '8': 0,  '7': 0}
        plain_pts_map = {'A': 11, '10': 10, 'K': 4, 'Q': 3,
                         'J': 2,  '9': 0,   '8': 0, '7': 0}

        for i, (tr, pl) in enumerate(zip(TRUMP_ORDER, PLAIN_ORDER)):
            ry = header_y + 18 + i * row_h
            tr_pts = trump_pts_map[tr]
            pl_pts = plain_pts_map[pl]
            tr_clr = '#ffe44d' if tr_pts >= 10 else ('#aaddff' if tr_pts > 0 else '#556677')
            pl_clr = '#ffe44d' if pl_pts >= 10 else (C_DIM if pl_pts > 0 else '#556677')
            self.cv.create_text(col_l, ry, anchor='nw',
                                text=f'{tr:<3} ({tr_pts})',
                                fill=tr_clr, font=('Helvetica', 12))
            self.cv.create_text(col_r, ry, anchor='nw',
                                text=f'{pl:<3} ({pl_pts})',
                                fill=pl_clr, font=('Helvetica', 12))

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
                                fill='white', font=('Helvetica', 11, 'bold'))

            # Label + click hint
            mid_x = sx + CW // 2 + (depth - 1) * 2
            self.cv.create_text(mid_x, sy + CH + 12, text=labels[team],
                                fill=colors[team], font=('Helvetica', 11, 'bold'))
            hint = '▲ close' if self.show_last_trick[team] else '▼ peek'
            self.cv.create_text(mid_x, sy + CH + 24, text=hint,
                                fill=C_GRAY, font=('Helvetica', 10))

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
                            font=('Helvetica', 12, 'bold'))

        for i, (pidx, card) in enumerate(last):
            cx = px + 10 + i * (mw + gap)
            cy = py + 22
            self._draw_mini_card(cx, cy, card)
            self.cv.create_text(cx + mw // 2, cy + mh + 9,
                                text=PLAYER_NAMES[pidx][:3],
                                fill=C_GRAY, font=('Helvetica', 10))

    def _draw_bid_action_labels(self):
        """Show each player's latest bid action (Passe / Prend / mode) near their seat."""
        CX, CY = self.CX, self.CY
        # Positions: inset from each player's edge toward the table center
        seats = {
            0: (CX,       CY + 80),   # South
            1: (CX + 145, CY),        # East
            2: (CX,       CY - 80),   # North
            3: (CX - 145, CY),        # West
        }
        for pidx, lbl in self.bid_actions.items():
            x, y = seats[pidx]
            is_pass = lbl == 'Passe'
            bg   = '#1a3a28' if is_pass else '#1a2e4a'
            fg   = C_GRAY   if is_pass else C_GOLD
            pad  = 10
            tw   = len(lbl) * 7 + pad * 2   # rough text width
            th   = 26
            self._rrect(x - tw // 2, y - th // 2, tw, th, r=8,
                        fill=bg, outline=fg, width=1)
            self.cv.create_text(x, y, text=lbl, fill=fg,
                                font=('Helvetica', 12, 'bold'), anchor='center')

    def _draw_trick_area(self):
        CX, CY = self.CX, self.CY
        self.cv.create_oval(CX-105, CY-110, CX+105, CY+110,
                            fill='', outline=C_GREEN, width=1, dash=(4, 4))

        if self.revealed_card and self.phase == 'bidding':
            rx = CX - (CW+10)//2
            ry = CY - (CH+14)//2
            self.cv.create_text(CX, ry-14, text='Carte retournée',
                                fill=C_GOLD, font=('Helvetica', 12, 'italic'))
            self._draw_card_face(rx, ry, self.revealed_card, large=True)
            self._draw_bid_action_labels()

        for pidx, card in self.trick:
            cx, cy = self._trick_xy[pidx]
            self._draw_card_face(cx - CW//2, cy - CH//2, card)

        if self.trick_pts[0] or self.trick_pts[1]:
            threshold = _score_threshold(self.trump)
            rx = self.W - SCORE_W - 8
            self.cv.create_text(rx, 12, anchor='ne',
                text=f'You+N: {self.trick_pts[0]}',
                fill=C_LIME, font=('Helvetica', 13, 'bold'))
            self.cv.create_text(rx, 28, anchor='ne',
                text=f'E+W: {self.trick_pts[1]}',
                fill='#fca5a5', font=('Helvetica', 13, 'bold'))
            self.cv.create_text(rx, 44, anchor='ne',
                text=f'need {threshold} to win',
                fill=C_GRAY, font=('Helvetica', 11))

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
        # East label above its cards
        n1 = len(self.hands[1])
        if n1 > 0:
            avail_v = self.H - 250
            sp1     = min(CH + 4, avail_v // max(n1, 1))
            east_top_y = max(self.CY - (sp1 * (n1 - 1) + CH) // 2, SIDE_CARD_MIN_Y)
            east_cx    = self.W - SCORE_W - CW - 12 + CW // 2
            self.cv.create_text(east_cx, east_top_y - 16,
                                text='East  (AI)', fill=C_TEXT,
                                font=('Helvetica', 14, 'bold'), anchor='center')
        n3 = len(self.hands[3])
        if n3 > 0:
            avail_v = self.H - 250
            sp3     = min(CH + 4, avail_v // max(n3, 1))
            west_top_y = max(self.CY - (sp3 * (n3 - 1) + CH) // 2, SIDE_CARD_MIN_Y)
            west_cx    = 70 + CW // 2
            self.cv.create_text(west_cx, west_top_y - 16,
                                text='West  (AI)', fill=C_TEXT,
                                font=('Helvetica', 14, 'bold'), anchor='center')

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
            sy = max(CY - (spread*(n-1) + CH) // 2, SIDE_CARD_MIN_Y)
            for i in range(n):
                self._draw_card_back(W - SCORE_W - CW - 12, sy + i*spread)
        elif pos == 'left':
            avail  = H - 250
            spread = min(CH + 4, avail // max(n, 1))
            sy = max(CY - (spread*(n-1) + CH) // 2, SIDE_CARD_MIN_Y)
            for i in range(n):
                self._draw_card_back(70, sy + i*spread)

    def _draw_contract_chip(self):
        if self.contract_player < 0 or not self.trump:
            return
        W, H, CX, CY = self.W, self.H, self.CX, self.CY
        # Place chip at top-right corner of each player's card area
        n0 = len(self.hands[0])
        avail  = W - 120
        spread = min(CW + 6, avail // max(n0, 1))
        south_right = CX + (spread * (max(n0, 1) - 1) + CW) // 2
        n_vert = max(len(self.hands[1]), len(self.hands[3]), 1)
        avail_v = H - 250
        spreadv = min(CH + 4, avail_v // n_vert)
        vert_top = CY - (spreadv * (n_vert - 1) + CH) // 2
        chip_pos = {
            0: (south_right + 14,          H - CH - 18),
            1: (W - SCORE_W - CW - 12 - 14,      vert_top),
            2: (CX + (spread * (max(len(self.hands[2]), 1) - 1) + CW) // 2 + 14, 68),
            3: (70 + CW + 14,              vert_top),
        }
        cpx, cpy = chip_pos[self.contract_player]
        r = 11
        self.cv.create_oval(cpx - r, cpy - r, cpx + r, cpy + r,
                            fill='#1a1a1a', outline=C_GOLD, width=3)
        self.cv.create_text(cpx, cpy, text='C',
                            fill=C_GOLD, font=('Helvetica', 12, 'bold'))

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
                                    fill=C_GOLD, font=('Helvetica', 14, 'bold'))
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
        ph     = 150
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
                fill=C_TEXT, font=('Helvetica', 14, 'bold'))

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
                font=('Helvetica', 17, 'bold'), tags=(tag,))
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
                font=('Helvetica', 17, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>', lambda e: self._on_bid_pass())
            self._bid_buttons[tag] = (bx, btn_y, bx + btn_w, btn_y + btn_h)

        else:
            revealed = self.revealed_card.suit
            best_lbl = (f'  |  best bid: {_mode_label(self.best_bid_mode)}'
                        f'  ({PLAYER_NAMES[self.best_bid_player]})'
                        if self.best_bid_mode else '')
            self.cv.create_text(px+pw//2, py+16,
                text=f'Tour de prise  –  Round 2  (not {revealed}){best_lbl}',
                fill=C_TEXT, font=('Helvetica', 14, 'bold'))

            # All 6 bid options + Pass = 7 buttons
            all_options = BID_MODES  # ♣ ♦ ♠ ♥ SA TA
            n_btns  = len(all_options) + 1  # +1 for pass
            btn_w   = min(100, (pw - 20) // n_btns - 6)
            btn_h   = 52
            btn_y   = py + ph//2 - btn_h//2 + 8
            total_w = n_btns * btn_w + (n_btns - 1) * 8
            bx0     = px + (pw - total_w) // 2

            for i, mode in enumerate(all_options):
                bx = bx0 + i * (btn_w + 8)
                tag = f'bid_mode_{mode}'
                available = (BID_RANK[mode] > self.best_bid_rank
                             and mode != revealed)
                if available:
                    if mode in ('SA', 'TA'):
                        fill, ol = self._btn_style(tag,
                                                   '#1a2e4a', '#4a9eff',
                                                   '#2a4a70', '#80c8ff')
                        ink = '#80c8ff' if self._bid_hover != tag else '#b0e0ff'
                    else:
                        fill, ol = self._btn_style(tag,
                                                   '#fefae0', C_GOLD,
                                                   '#fff8b0', '#ffe44d')
                        ink = C_RED if (mode in SUIT_RED and SUIT_RED[mode]) else C_BLACK
                    self._rrect(bx, btn_y, btn_w, btn_h, r=8,
                                fill=fill, outline=ol, width=2, tags=(tag,))
                    lbl = mode
                    fsz = ('Helvetica', 27) if mode in SUITS else ('Helvetica', 16, 'bold')
                    self.cv.create_text(bx + btn_w//2, btn_y + btn_h//2,
                        text=lbl, fill=ink, font=fsz, tags=(tag,))
                    self.cv.tag_bind(tag, '<Button-1>',
                                     lambda e, m=mode: self._on_bid_take(m))
                    self._bid_buttons[tag] = (bx, btn_y, bx + btn_w, btn_y + btn_h)
                else:
                    # Grayed-out unavailable option
                    self._rrect(bx, btn_y, btn_w, btn_h, r=8,
                                fill='#1a1a1a', outline='#444', width=1)
                    lbl = mode
                    fsz = ('Helvetica', 27) if mode in SUITS else ('Helvetica', 16, 'bold')
                    ink_dim = C_RED if (mode in SUITS and SUIT_RED[mode]) else '#555'
                    self.cv.create_text(bx + btn_w//2, btn_y + btn_h//2,
                        text=lbl, fill=ink_dim, font=fsz)

            # Pass button (round 2)
            bx  = bx0 + len(all_options) * (btn_w + 8)
            fill, ol = self._btn_style('bid_pass2',
                                       '#3d1818', '#c03030',
                                       '#5c2222', '#e84040')
            tag = 'bid_pass2'
            self._rrect(bx, btn_y, btn_w, btn_h, r=8,
                        fill=fill, outline=ol, width=2, tags=(tag,))
            self.cv.create_text(bx + btn_w//2, btn_y + btn_h//2,
                text='Pass', fill=C_TEXT,
                font=('Helvetica', 16, 'bold'), tags=(tag,))
            self.cv.tag_bind(tag, '<Button-1>', lambda e: self._on_bid_pass())
            self._bid_buttons[tag] = (bx, btn_y, bx + btn_w, btn_y + btn_h)

        if self._bid_pass_flash:
            self._rrect(px + pw//2 - 90, py + 20, 180, 80, r=10,
                        fill='#1b4332', outline=C_LIME, width=3)
            self.cv.create_text(px + pw//2, py + 60,
                text='Passed  ✓', fill=C_LIME,
                font=('Helvetica', 19, 'bold'))

    # ── Annonce overlay ────────────────────────────────────────────────────────
    def _draw_annonce_panel(self):
        W, H = self.W, self.H
        ow = min(520, W - 40)
        ox = (W - ow) // 2
        all_ann = [(pidx, self.annonces[pidx]) for pidx in range(4) if self.annonces[pidx]]
        oh = 80 + max(len(all_ann), 1) * 26 + 60
        oy = (H - oh) // 2
        self._rrect(ox, oy, ow, oh, r=16, fill='#0a2218', outline=C_GOLD, width=3)
        self.cv.create_text(ox + ow // 2, oy + 22,
                            text='Annonces', fill=C_GOLD,
                            font=('Helvetica', 18, 'bold'))
        y = oy + 48
        if not all_ann:
            self.cv.create_text(ox + ow // 2, y + 10,
                                text='No annonces this round',
                                fill=C_GRAY, font=('Helvetica', 14, 'italic'))
            y += 26
        else:
            for pidx, anns in all_ann:
                parts = []
                for a in sorted(anns, key=lambda x: -x['pts']):
                    if a['type'] == 'carre':
                        parts.append(f"Carre {a['rank']}s ({a['pts']})")
                    else:
                        parts.append(f"Suite-{a['len']} {a['suit']} to {a['top']} ({a['pts']})")
                self.cv.create_text(ox + 18, y, text=f'{PLAYER_NAMES[pidx]}:',
                                    fill=C_TEXT, font=('Helvetica', 13, 'bold'), anchor='nw')
                self.cv.create_text(ox + 100, y, text='  '.join(parts),
                                    fill=C_GOLD, font=('Helvetica', 13), anchor='nw')
                y += 26
        if self.annonce_winner_team >= 0:
            teams = ['You & North', 'East & West']
            wt  = self.annonce_winner_team
            msg = f'{teams[wt]} win annonces  +{self.annonce_pts[wt]} pts'
            clr = C_LIME if wt == 0 else '#fca5a5'
        else:
            msg = 'Annonces void' if all_ann else ''
            clr = C_GRAY
        if msg:
            self.cv.create_text(ox + ow // 2, y + 14, text=msg,
                                fill=clr, font=('Helvetica', 14, 'bold'))
        tag = 'ann_play_btn'
        by  = oy + oh - 42
        self._rrect(ox + ow // 2 - 70, by, 140, 32, r=8,
                    fill='#1b4332', outline=C_GOLD, width=2, tags=(tag,))
        self.cv.create_text(ox + ow // 2, by + 16,
                            text='Play ▶', fill='white',
                            font=('Helvetica', 15, 'bold'), tags=(tag,))
        self.cv.tag_bind(tag, '<Button-1>', lambda e: self._start_play())

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
                            font=('Helvetica', 18, 'bold'))
        self.cv.create_text(ox+ow//2, oy+52,
                            text=res_text, fill=res_color,
                            font=('Helvetica', 16, 'bold'))

        trump_ink = C_RED if (self.trump in SUIT_RED and SUIT_RED[self.trump]) else C_TEXT
        threshold = _score_threshold(self.trump)
        lines = [
            (f"Mode: {_mode_label(self.trump)}  |  Takers: {team_names[ct]}", trump_ink),
            ('', C_TEXT),
            (f"{team_names[ct]}  trick pts: {ri.get('taker_trick_pts', 0)}  (need {threshold})", C_TEXT),
            (f"{team_names[at]}  trick pts: {ri.get('def_trick_pts', 0)}", C_TEXT),
        ]
        if ri.get('belote_team') is not None:
            bteam = team_names[ri['belote_team']]
            lines.append((f"Belote: {bteam} +20 pts  (imprenable)", '#ff9f40'))
        ann_w = ri.get('ann_winner', -1)
        ann_p = ri.get('ann_pts', [0, 0])
        if ann_w >= 0:
            lines.append((f"Annonces: {team_names[ann_w]} +{ann_p[ann_w]} pts", C_GOLD))
        lines += [
            ('', C_TEXT),
            (f"{team_names[ct]}  total: {ri.get('taker_pts', 0)}", C_TEXT),
            (f"{team_names[at]}  total: {ri.get('def_pts', 0)}", C_TEXT),
        ]

        for i, (ln, clr) in enumerate(lines):
            self.cv.create_text(ox+ow//2, oy+80 + i*22,
                                text=ln, fill=clr, font=('Helvetica', 14))

        sep_y = oy + 80 + len(lines) * 22 + 6
        self.cv.create_line(ox+30, sep_y, ox+ow-30, sep_y,
                            fill='#2d6a4f', width=1)
        self.cv.create_text(ox+ow//2, sep_y+14,
                            text='Running scores:', fill=C_GRAY,
                            font=('Helvetica', 13))
        self.cv.create_text(ox+ow//2, sep_y+32,
                            text=f'You & North: {self.scores[0]}   '
                                 f'East & West: {self.scores[1]}',
                            fill=C_TEXT, font=('Helvetica', 14, 'bold'))

        tag = 'next_round'
        self._rrect(ox+ow//2-70, oy+oh-44, 140, 34, r=8,
                    fill='#991b1b', outline=C_GOLD, width=2, tags=(tag,))
        self.cv.create_text(ox+ow//2, oy+oh-27,
                            text='Next round ▶', fill='white',
                            font=('Helvetica', 15, 'bold'), tags=(tag,))
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
                            font=('Helvetica', 21, 'bold'))
        self.cv.create_text(ox+ow//2, oy+80,
                            text=f'  {team} win!', fill=color,
                            font=('Helvetica', 18, 'bold'))
        self.cv.create_text(ox+ow//2, oy+120,
                            text=f'Final: You & North {self.scores[0]}   '
                                 f'East & West {self.scores[1]}',
                            fill=C_TEXT, font=('Helvetica', 15))

        tag = 'new_game_btn'
        self._rrect(ox+ow//2-80, oy+oh-54, 160, 38, r=8,
                    fill='#991b1b', outline=C_GOLD, width=2, tags=(tag,))
        self.cv.create_text(ox+ow//2, oy+oh-35,
                            text='New Game', fill='white',
                            font=('Helvetica', 16, 'bold'), tags=(tag,))
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
        self.annonces           = [[], [], [], []]
        self.annonce_winner_team = -1
        self.annonce_pts        = [0, 0]
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
        self.best_bid_rank   = 0
        self.best_bid_player = -1
        self.best_bid_mode   = None
        self.bid_actions     = {}
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
        if self.trump in ('SA', 'TA'):
            return
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
            if ai_bid_round1(self.hands[pidx], self.revealed_card, self._bid_count):
                self._apply_take(pidx, None)
            else:
                self._apply_pass(pidx)
        else:
            mode = ai_bid_round2(self.hands[pidx], self.revealed_card.suit,
                                 self.best_bid_rank, self._bid_count)
            if mode:
                self._apply_bid_r2(pidx, mode)
            else:
                self._apply_pass(pidx)

    def _apply_take(self, pidx: int, suit: Optional[str]):
        trump = suit if suit else self.revealed_card.suit
        self.trump           = trump
        self.contract_player = pidx
        mode_label = _mode_label(trump)
        self.bid_actions[pidx] = f'Prend  {mode_label}'
        self.status.config(
            text=f'{PLAYER_NAMES[pidx]} takes – {mode_label}  '
                 f'({"round 1" if self.bid_round == 1 else "round 2"})')
        self._deal_remaining(pidx)
        self._detect_belote()
        self._compute_annonces()
        self._show_announcing()

    def _apply_bid_r2(self, pidx: int, mode: str):
        """Player makes a competitive bid in round 2."""
        rank = BID_RANK[mode]
        if rank > self.best_bid_rank:
            self.best_bid_rank   = rank
            self.best_bid_player = pidx
            self.best_bid_mode   = mode
        self.bid_actions[pidx] = _mode_label(mode)
        self.status.config(
            text=f'{PLAYER_NAMES[pidx]} bids {_mode_label(mode)}'
                 f'  (best so far: {_mode_label(self.best_bid_mode)})')
        self._bid_count += 1
        self._redraw()
        if self._bid_count == 4:
            self.root.after(500, lambda: self._apply_take(
                self.best_bid_player, self.best_bid_mode))
        else:
            self.current = (pidx + 3) % 4
            if self.current != 0:
                self.root.after(700, self._ai_bid_step)

    def _compute_annonces(self):
        for pidx in range(4):
            self.annonces[pidx] = detect_annonces(self.hands[pidx])
        wt = ann_winner_team(self.annonces, self.trump)
        self.annonce_winner_team = wt
        if wt >= 0:
            self.annonce_pts[wt] = sum(
                a['pts'] for pidx in range(4) if pidx % 2 == wt
                for a in self.annonces[pidx]
            )

    def _show_announcing(self):
        self.phase = 'announcing'
        self.status.config(text='Annonces – click anywhere to play')
        self._redraw()

    def _apply_pass(self, pidx: int):
        self.bid_actions[pidx] = 'Passe'
        self.status.config(text=f'{PLAYER_NAMES[pidx]} passes')

        if self.bid_round == 1:
            self._bid_count += 1
            if self._bid_count == 4:
                self.bid_round       = 2
                self._bid_count      = 0
                self.best_bid_rank   = 0
                self.best_bid_player = -1
                self.best_bid_mode   = None
                self.current         = (self.dealer + 1) % 4
                self.status.config(text='Bidding phase – round 2')
                self._redraw()
                if self.current != 0:
                    self.root.after(700, self._ai_bid_step)
            else:
                self.current = (pidx + 3) % 4
                self._redraw()
                if self.current != 0:
                    self.root.after(700, self._ai_bid_step)
        else:
            # Round 2: count turns (pass or bid), resolve after all 4 have gone
            self._bid_count += 1
            self._redraw()
            if self._bid_count == 4:
                if self.best_bid_mode is not None:
                    self.root.after(500, lambda: self._apply_take(
                        self.best_bid_player, self.best_bid_mode))
                else:
                    self.dealer = (self.dealer + 3) % 4
                    self.status.config(text='No takers – redealing…')
                    self._redraw()
                    self.root.after(1200, self._new_round)
            else:
                self.current = (pidx + 3) % 4
                if self.current != 0:
                    self.root.after(700, self._ai_bid_step)

    def _on_bid_take(self, suit_or_mode: Optional[str]):
        if self.bid_round == 1:
            self._apply_take(0, suit_or_mode)
        else:
            self._apply_bid_r2(0, suit_or_mode)

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
        self.current = (self.dealer + 3) % 4
        self.status.config(text=f'Playing  –  {_mode_label(self.trump)}')
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
            self.current = (pidx + 3) % 4
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
        # Belote always imprenable; annonce pts go to the winning annonce team
        ann_ct = self.annonce_pts[ct] if self.annonce_winner_team == ct else 0
        ann_at = self.annonce_pts[at] if self.annonce_winner_team == at else 0

        all_to_ct = (self.tricks_won[at] == 0)
        all_to_at = (self.tricks_won[ct] == 0)

        belote_team = (self.belote_player % 2
                       if self.belote_player >= 0 and self.belote_played > 0
                       else None)

        if all_to_ct or all_to_at:
            w, l   = (ct, at) if all_to_ct else (at, ct)
            result = 'capot'
            # Winner gets all trick pts + belote (both sides) + their annonces; loser keeps belote + their annonces
            self.scores[w] += (taker_trick + def_trick
                               - self.belote_pts[l]
                               + self.belote_pts[w]
                               + self.annonce_pts[w]
                               + self.litige_pts)
            self.scores[l] += self.belote_pts[l] + self.annonce_pts[l]
            self.litige_pts = 0
            taker_pts = taker_trick + self.belote_pts[ct] + ann_ct
            def_pts   = def_trick   + self.belote_pts[at] + ann_at
        elif taker_trick >= _score_threshold(self.trump):
            result = 'success'
            taker_pts = taker_trick + self.belote_pts[ct] + ann_ct
            def_pts   = def_trick   + self.belote_pts[at] + ann_at
            self.scores[ct] += taker_pts + self.litige_pts
            self.scores[at] += def_pts
            self.litige_pts  = 0
        else:                            # chute
            result = 'chute'
            full_pts = _full_trick_pts(self.trump)
            taker_pts = self.belote_pts[ct] + ann_ct
            def_pts   = full_pts + self.belote_pts[at] + ann_at + self.litige_pts
            self.scores[ct] += taker_pts
            self.scores[at] += def_pts
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
            'ann_winner':      self.annonce_winner_team,
            'ann_pts':         list(self.annonce_pts),
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

        self.dealer = (self.dealer + 3) % 4
        self.status.config(text='Round over – see results')
        self.phase = 'gameover' if max(self.scores) >= WIN_TARGET else 'scoring'
        self._redraw()

    # ── Click handling ─────────────────────────────────────────────────────────
    def _on_canvas_click(self, event):
        if self.phase == 'announcing':
            self._start_play()
            return
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
