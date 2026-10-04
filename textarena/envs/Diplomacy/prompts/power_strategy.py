"""Per-power strategy advice shown in each player's opening prompt.

Adapted from the AI_Diplomacy project (https://github.com/Alx-AI/AI_Diplomacy).
Kept as Python strings so the text ships with the package.
"""

POWER_STRATEGY = {
    "AUSTRIA": """Dear Austria,
They say you're surrounded - but that means you can strike in any direction. History shows the strongest Austrian players turn early vulnerability into mid-game dominance through decisive action toward those vital 18 centers, not just survival.

Key insights:
- Prevent Russia-Turkey alliance above all else
- Italy must be friend or dead quickly (95% of A/I wars kill both)
- Serbia is crucial 1901 - secure it
- Galicia bounce often vital Spring 1901
- Central position enables striking anywhere once secured

Critical mindset: You're not playing to survive - you're playing to explode out from the center. Yes, early diplomacy keeps you alive, but it should serve your offensive goals, not replace them.

Paths to victory often require:
1. Securing strong early alliance (usually Italy or Russia)
2. Eliminating one neighbor completely by 1904
3. Leveraging central position for unexpected strikes
4. Breaking stalemate line via Munich/Berlin

Don't fall into defensive play just because everyone expects it. Stats show Austrian solos often come from players who turn the early "defensive" moves into aggressive positioning by year 3.

Time works against you - the longer you wait, the more likely others unite. Make your decisive moves by mid-game, usually years 3-4. Better to strike imperfectly than wait for perfect alignment.

The throne of Europe awaits. Show them that the "weakest" starting position was merely gathering strength to strike.""",
    "ENGLAND": """Dear England,

Your island position tempts defensive play. Resist this. The North Sea is not a moat to hide behind, but a highway to those crucial 18 centers. The most successful English players use their naval superiority to project power aggressively.

Key insights:
- Secure North Sea early - it's your lifeline
- Norway is nearly guaranteed - but don't stop there
- Must ally one of France/Germany against the other
- Fleet positioning is everything - control key waters early

Critical mindset: You're not playing defense, you're controlling the seas to enable offense. Every fleet should be positioned with attack in mind. Top players even use the threat of attacks to extract concessions: "Let me have Belgium or I'll support France in."

Winning paths usually require:
1. Dominating Scandinavia quickly
2. Eliminating one neighbor decisively
3. Getting fleets into Mediterranean
4. Securing that crucial 18th center (often Tunis or Moscow)

Don't fall into the "defensive England" trap. Yes, you're hard to invade, but you can't win by turtling. The stats show successful English players often strike aggressively in years 2-3, not waiting for the perfect moment that never comes.

Your fleets are your strength - use them to strangle opponents' growth while you expand. Better to risk early aggression than watch others grow too strong to stop.

Rule the waves actively, not passively. The crown of Europe awaits those bold enough to seize it.""",
    "FRANCE": """Dear France,

You start in perhaps the strongest position. Don't waste it with hesitation. History shows successful French players strike early and decisively - aiming for 5-6 centers by 1902 is not just possible, but often optimal on the path to 18.

Key insights:
- Early momentum is crucial - Spain, Portugal, Belgium all within reach 1901
- Choose England or Germany as initial ally/target - fighting both is fatal
- Your dual coasts (Brest/Marseilles) let you project power both directions
- Tunis often proves critical for French solos - plan your Med strategy early

The trap many fall into: playing too conservatively because the position feels secure. Don't. Your corner position is not a fortress to hide in, but a springboard for conquest. The stats are clear - France wins most when acting decisively in the first 2-3 years.

Watch for these opportunities:
- England/Germany friction you can exploit
- Italy focused east (leaving their rear exposed)
- Early builds that let you dominate multiple seas

Your path to victory requires crossing the stalemate line. Usually this means either:
1. Mediterranean dominance + push through Munich
2. Northern control + grab of Tunis
3. Both, if you're bold enough

Time is not your ally - other powers grow stronger while you wait. Make your moves early, build aggressively, and always be working toward that 18th center. Better to fail spectacularly pushing for a win than survive passively into a draw.

The throne of Europe is yours to lose. Show them French audacity still rules the continent.""",
    "GERMANY": """Dear Germany,
Your central position offers unmatched opportunity - but only if you seize it. Ten centers lie within two moves of your starting position - a strong foundation for reaching those vital 18 centers needed for victory.

Key insights:
- Must secure at least one strong ally early (usually England or France)
- Denmark is yours, but Belgium/Holland require decisive action
- Naval weakness must be addressed - either through alliances or builds
- Central position lets you strike any direction - use this flexibility

Critical mindset: You're not a buffer state - you're the hammer of Europe. Top German players shape the game's direction through decisive action, not reactive diplomacy. Yes, you need allies, but you also need to be feared.

Paths to victory often involve:
1. Securing your choice of early allies through bold offers
2. Eliminating one neighbor completely by 1904
3. Leveraging central position to strike unexpected directions
4. Taking key centers across stalemate line (usually through Russia)

Don't play the mediator unless it's part of your path to victory. Your central position is not a curse but a gift - you can strike anywhere. History shows German solos often come from players who acted decisively in years 2-3.

Time works against you - the longer you wait, the more likely others unite against your central position. Make your moves early, build purposefully, and always be working toward that 18th center.

The heart of Europe is yours. Show them why the center controls the periphery.""",
    "ITALY": """Dear Italy,
They call you the weakest power. Prove them wrong. Your position requires finesse, but victory comes to those who act decisively toward 18 centers, not those who wait. The successful Italian creates opportunities rather than just reacting to them.

Key insights:
- Austria must be friend or dead (95% of early A/I wars kill both)
- Tunis is guaranteed, but don't stop there
- Your fleet position can dominate the Mediterranean
- You can influence both East and West uniquely

Critical mindset: You're not the weak power waiting for others' mistakes. You're the opportunistic power creating situations you can exploit. The best Italian players actively shape the diplomatic landscape while appearing reactive.

Paths to victory often require:
1. Securing strong early position (usually via Austrian alliance)
2. Dominating Mediterranean waters
3. Striking decisively when others are distracted
4. Expanding into either France or Turkey decisively

Don't wait for the perfect moment - it rarely comes. Create your opportunities through active diplomacy and positioned strikes. Yes, patience matters, but passive play leads to slow death.

Time is actually against you - the longer the game goes, the more likely others are to grow too strong. Make your moves when opportunities arise, usually years 3-4.

The Mediterranean throne awaits. Show them Italian "weakness" was always just disguised strength.""",
    "RUSSIA": """Dear Russia,

You command the largest starting position and the most units. Don't let this abundance paralyze you with choices. The best Russian players act decisively while maintaining strategic flexibility on their path to 18 centers.

Key insights:
- You can secure two builds 1901 (Sweden/Rumania) if aggressive
- Must prevent or bounce Turkey in Black Sea early
- St. Petersburg is crucial - almost no Russian solos exclude it
- You can influence both north and south theaters

Critical mindset: You're not just managing two fronts - you're exploiting them. When pressure comes from one direction, strike in the other. Your size is an advantage only if you use it actively.

Paths to victory often require:
1. Securing at least one front through strong alliances
2. Eliminating at least one neighbor by 1904
3. Maintaining presence in both north and south
4. Strategic betrayal of a long-term ally

Don't fall into defensive play when attacked - counter-attack elsewhere. Statistics show successful Russians often trade space for time in one theater while expanding aggressively in another.

The longer the game goes, the more likely others unite against your size. Make your decisive moves by mid-game, usually years 3-4. Better to strike imperfectly than wait for perfect alignment.

The twin crowns of north and south await. Show them why the Russian bear strikes with both paws.""",
    "TURKEY": """Dear Turkey,

Your corner position is a fortress - but fortresses don't win games. The most successful Turkish players use their defensive strength as a platform for aggressive expansion toward those vital 18 centers, not just survival.

Key insights:
- Black Sea control is crucial - bounce or take it 1901
- Must prevent or survive early Russia/Austria alliance
- Your position strengthens dramatically if you survive to 1904
- Fleet position can dominate eastern Mediterranean

Critical mindset: You're not playing to survive - you're playing to explode out of your corner. Yes, defense matters early, but it should enable your offensive preparations, not replace them.

Paths to victory often require:
1. Securing one strong ally against the other (Russia or Austria)
2. Eliminating one neighbor completely by 1904
3. Breaking into Mediterranean decisively
4. Getting fleets into position for late-game strikes west

Don't fall into the "turtle Turkey" trap. While you can often survive playing purely defensively, you can't win that way. The stats show Turkish solos often come from players who defend selectively while preparing aggressive breakouts.

Time can work for you - but only if you're actively preparing your offensive positions. Build purposefully, negotiate actively, and always be ready to exploit opportunities for expansion.

The crown of Europe lies west of your fortress. Show them the Sick Man of Europe was merely gathering strength to strike.""",
}
