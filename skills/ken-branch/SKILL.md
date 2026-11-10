---
name: ken-branch
description: Reference used inside every mode - when to offer a branch for a gap found mid-study, and how to record the learner's decision (piece, learned before, topic of its own, note, declined). Not a mode.
modes: []
---

# ken-branch (shared reference)

Most gaps found mid-study are pieces of the thing being studied. Watch for them in every mode.

**Offer a branch when** they ask "what is X?" mid-reasoning; they name the hole themselves; you had
to teach a term not on the syllabus; a placement answer missed; the same misunderstanding shows up
twice; or a reached scout's gap shows.

**Offer it in one line, and let them decide:**

| decision | when | command |
|---|---|---|
| a piece | they cannot carry the concept without it; 1-3 concepts | `ken branch <topic> <concept> "DOMAIN :: NAME :: DESC" --by tutor` |
| learned before | it comes first rather than inside | add `--before` |
| a topic of its own | its own goal, about five concepts or more, or other topics would use it | add `--topic NEW --title "..."` |
| a note | they could step past it for now | `--note "..."` |
| declined | they say no | `--decline "..."` |

`--by learner` when they raised it before any offer; `--by tutor` when you offered it; a scouted or
tool offer is decided with `--source scout:N` / `--source KEY` (`--by tool`, or `--by learner` when
they raised it first). Record every offer, the declined ones too: `ken branch <topic>` reads them
back as offer quality. Pieces nest at most two deep.

Once a concept has pieces, ask them to recall the pieces from memory before teaching the whole
again: `ken recall <topic> <concept> --listed "first; second"`. `ken map <topic>` shows each
concept climbed, ready, or waiting on its pieces.

## Move through a web of pyramids

Topics are made of topics at every level, and any idea can be the top of its own pyramid. Pieces can
be shared, so moving down, up and sideways are all normal, in any order that helps.

- **Grow the map from use.** Do not map a whole topic up front. When an idea stalls, break it into a
  few pieces and ask which feels like the problem.
- **Mark and trail.** Record their pick with `ken mark <topic> <concept> problem|fuzzy|solid`; it moves
  what comes next and never credit. Going down: `ken trail <topic> <concept> --why "..."`; `--back`
  returns. When adding a piece with `ken branch`, add `--predict problem|solid`, so `ken branch <topic>`
  can grade your guess.
- **Check the pick.** Their pick says where to start; one small problem checks it, because some real
  gaps feel solid. The check is teaching, so it is not recorded.
- **Keep the trail.** Say what led here and return to the question that started it, so going down
  cannot drift away from the goal.
- **Wide, then deep.** Give the overview first. Gaps found in the depth become more pieces to move to.
