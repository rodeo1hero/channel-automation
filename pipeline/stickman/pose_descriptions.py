"""Plain-English descriptions of each named pose, used as edit instructions
when generating the AI-rendered character sprite sheet
(pipeline/character_gen.py / scripts/generate_character.py). Each
description bakes in a matching facial expression -- the renderer treats
pose and expression as one combined sprite rather than separate layers, so
personality comes from picking the right pose for the moment rather than
compositing a face on top. Keep these in sync with the pose vocabulary in
pipeline/stickman/actions.py's HOLD_ACTIONS."""

# The "core" set gets heavy screen time (narration relies on these constantly), so
# they're always generated one-per-call for full resolution/sharpness. Everything else
# ("long tail" -- business/money, rare reactions) is generated in batched grid sheets
# instead, which is ~4-8x cheaper per pose at the cost of some sharpness after
# upscaling -- an acceptable tradeoff for poses that show up occasionally, not one
# you'd want for e.g. "stand" or "walk", which are on screen most of every video. See
# pipeline/character_gen.py's ensure_outfit_sprites/generate_pose_grid.
CORE_POSES = {
    "stand", "walk_a", "walk_b", "run_a", "run_b", "point_right", "point_left",
    "wave", "think", "shrug", "arms_crossed", "sit", "surprised", "celebrate",
    "explain", "nod",
}

POSE_DESCRIPTIONS = {
    "stand": ("standing relaxed, friendly neutral expression with a slight closed-mouth "
              "smile, arms hanging naturally at the sides, facing forward"),
    "walk_a": ("mid-stride walking to the right, confident focused expression: right leg "
               "forward and bent, left leg trailing back, arms swinging naturally in "
               "opposition to the legs (left arm forward, right arm back)"),
    "walk_b": ("mid-stride walking to the right, confident focused expression: left leg "
               "forward and bent, right leg trailing back, arms swinging naturally in "
               "opposition to the legs (right arm forward, left arm back)"),
    "run_a": ("running to the right, mid-stride, more exaggerated than walking, "
              "determined excited expression: right leg driving forward and bent high, "
              "left leg trailing back, arms pumping hard in opposition to the legs, torso "
              "leaning forward"),
    "run_b": ("running to the right, mid-stride, more exaggerated than walking, "
              "determined excited expression: left leg driving forward and bent high, "
              "right leg trailing back, arms pumping hard in opposition to the legs, "
              "torso leaning forward"),
    "point_right": ("standing, confident engaged expression with eyebrows slightly "
                     "raised, one arm raised and fully extended straight out to the right "
                     "at shoulder height, pointing with the hand; the other arm relaxed "
                     "at the side"),
    "point_left": ("standing, confident engaged expression with eyebrows slightly "
                    "raised, one arm raised and fully extended straight out to the left "
                    "at shoulder height, pointing with the hand; the other arm relaxed "
                    "at the side"),
    "wave": ("standing, warm happy smile with eyes crinkled, one arm raised up and bent, "
              "hand near head height as if waving hello; the other arm relaxed at the "
              "side"),
    "think": ("standing, pensive thoughtful expression -- eyes looking upward, one "
              "eyebrow raised, slight frown -- head tilted slightly, one hand raised to "
              "the chin in a thinking/pondering gesture, the other arm relaxed at the "
              "side"),
    "shrug": ("standing, eyebrows raised high and mouth in a flat uncertain line, both "
              "arms raised out to the sides with elbows bent and hands up near shoulder "
              "height, palms up, in a shrugging 'I don't know' gesture, shoulders "
              "raised"),
    "arms_crossed": ("standing, skeptical unimpressed expression with one eyebrow raised "
                      "and a flat mouth, both arms crossed over the chest"),
    "sit": ("sitting cross-legged on the ground, both hands resting flat on top of the "
            "knees with palms down, relaxed content expression with a light smile, "
            "looking forward"),
    "surprised": ("standing, shocked surprised expression -- eyes wide open, eyebrows "
                  "raised high, mouth open in a round 'O' shape -- both arms thrown "
                  "straight up in the air above the head"),
    "celebrate": ("standing, big excited open-mouth grin with bright happy eyes, both "
                  "arms thrown straight up in the air above the head in a triumphant, "
                  "cheering gesture"),
    "explain": ("standing, confident engaged expression as if mid-speech, eyebrows "
                "slightly raised, both arms held out to the sides and slightly forward, "
                "palms up, in an open explaining/presenting gesture"),
    "nod": ("standing relaxed, warm agreeable smile with eyes slightly closed as if "
            "nodding in agreement, head tilted down slightly, arms hanging naturally at "
            "the sides"),
    "reading_desk": ("sitting at a simple wooden desk with an open book in front, one "
                      "hand resting on the page, a small desk lamp beside the book; "
                      "focused thoughtful expression, eyes looking down at the page, "
                      "slight furrowed brow of concentration"),
    "laptop": ("sitting cross-legged on the floor with an open laptop on the lap, both "
               "hands near the keyboard as if typing; focused concentrating expression "
               "with a slightly furrowed brow"),
    "relaxed_chair": ("sitting back in a simple armchair, legs crossed, one arm resting "
                       "on the chair's armrest; relaxed content expression with a small "
                       "satisfied smug smile"),

    # --- Business & money set -------------------------------------------
    "holding_money": ("standing, holding a thick stack of banknotes in one hand, showing "
                       "it out toward the viewer, confident pleased expression with a "
                       "smile"),
    "counting_money": ("standing, both hands counting through a stack of banknotes held "
                        "in front of the chest, focused satisfied expression"),
    "looking_cash": ("standing, looking down at a large pile of cash on the ground in "
                      "front of them, impressed admiring expression with raised "
                      "eyebrows"),
    "gold_coin": ("standing, holding a single large gold coin up at eye level in one "
                  "hand, examining it, pleased curious expression"),
    "stock_up": ("standing beside a large simple green bar chart with an upward-trending "
                 "arrow floating next to them, pointing at the chart with one hand, "
                 "excited pleased expression"),
    "stock_down": ("standing beside a large simple red bar chart with a downward-trending "
                   "arrow floating next to them, one hand on the chin, worried concerned "
                   "expression"),
    "calculator": ("standing, holding a calculator in one hand and pressing a button "
                   "with the other, focused concentrating expression"),
    "financial_report": ("standing, holding up an open financial report document with "
                          "visible chart lines on the page, presenting it outward toward "
                          "the viewer, confident engaged expression"),
    "laptop_stand": ("standing, holding an open laptop in both hands at chest height, "
                      "looking down at the screen, focused engaged expression"),
    "handshake": ("standing, shaking hands with a second plain generic figure drawn in "
                  "the exact same simple line-art style -- a featureless silhouette in a "
                  "plain black suit with no laurel wreath, hat, or other distinguishing "
                  "details -- standing beside them facing our character, both figures' "
                  "extended arms meeting in a handshake in the middle; our character has "
                  "a friendly confident expression, full width of both figures visible"),
    "business_deal": ("sitting at a simple desk across from a second plain generic figure "
                       "drawn in the exact same simple line-art style -- a featureless "
                       "silhouette in a plain black suit with no laurel wreath, hat, or "
                       "other distinguishing details -- the two exchanging a signed "
                       "document across the desk; our character has a confident satisfied "
                       "expression, full width of both figures and the desk visible"),
    "adjust_tie": ("standing, one hand adjusting or straightening a necktie at the "
                   "collar, composed confident expression"),
    "money_celebrate": ("standing, both arms thrown straight up in the air in a "
                        "triumphant cheering gesture, big excited grin, banknotes falling "
                        "and scattered in the air around them like confetti"),
    "bankrupt": ("sitting on the ground, shoulders slumped, both front pockets visibly "
                 "turned inside out and empty, disappointed sad expression looking "
                 "down"),
    "rich_lifestyle": ("standing, one arm leaning casually on the hood of a sleek shiny "
                       "car beside them, other hand in pocket, smug confident expression, "
                       "small sunglasses"),
    "broke": ("sitting on the ground, head down, holding an open empty wallet with both "
              "hands, sad dejected expression"),
}
