# Executive Research Brief

[Visual Dashboard](https://htmlpreview.github.io/?https://github.com/syst0m/demiurge/blob/main/skills/marcus/human-only/demiurge-brief.html)

The gist below is generated from the HTML brief. Run `python scripts/sync_brief_summary.py` to refresh it.

<!-- BEGIN DEMIURGE BRIEF GIST -->
```mermaid
flowchart TD
    subgraph Dashboard["DEMIURGE VISUAL DASHBOARD PREVIEW"]
        direction TB
        subgraph S1["§01 Four Empirical Constants"]
            direction LR
            N1["<b>7,560 Runs</b><br/>0% Skill Lift"]
            N2["<b>2.12× Risk</b><br/>Script Flaws"]
            N3["<b>~15,000 Scale</b><br/>Break-Even"]
            N4["<b>7–33% Unsafe</b><br/>Action Rate"]
        end
        subgraph S2["§02 Graded Evidence Base"]
            direction LR
            E1["<b>[SETTLED]</b><br/>Harness > Model<br/>Gates > Prompts<br/>Safety ⟂ Success"]
            E2["<b>[CONTESTED]</b><br/>Rejection > Generation<br/>Curation > Automation"]
            E3["<b>[EMERGING]</b><br/>Self-Harness Loops<br/>Regression Gating"]
        end
        subgraph S3["§03 Mechanical Gate Pipeline"]
            direction LR
            G0["G0: Intake"] --> G1["G1: Base"] --> G2["G2: Contrast"] --> G3["G3: Draft"] --> G4["G4: Validate"] --> G5["G5: Prove"] --> G6["G6: Register"]
        end
        subgraph S4["§04–05 Invariant Verification & Limits"]
            direction LR
            V1["<b>Verification</b><br/>Gate Regression Suite<br/>0 Blocking Issues"]
            V2["<b>Honest Limits</b><br/>No Unmeasured Lift<br/>Automated Design Ceiling"]
        end
        S1 --> S2 --> S3 --> S4
    end
```

## Four Empirical Constants That Shaped the Design

- **7,560**: runs in the only large controlled test of generated skills — which found no improvement over no skill at all
- **2.12×**: more likely to carry a vulnerability when a skill bundles executable scripts
- **~15,000**: deployed examples before automated design paid for itself — and only on two datasets of those tested
- **7–33%**: unsafe-action rate across fully scaffolded agents, uncorrelated with their task success

## Core Architectural Takeaways

- **Rejection Outweighs Generation:** Methods that achieve real performance lift (e.g., SkillCAT +49.7%) succeed by ruthlessly discarding candidates through contrastive test replay, not through speculative prompt generation.
- **The Harness Dominates the Model:** Model×harness pairing varies completion and efficiency dramatically across execution trajectories—enough to invert raw model leaderboard rankings.
- **Capability and Safety Are Orthogonal:** Unsafe-action rates (7–33%) do not track task success rates (39–64%). Scaling capability without mechanical write-gates amplifies vulnerability.
- **Four-Tier Trust Model (T1 to T4):** Each skill carries a provenance tier. T1 is user-written or factory-built and accepted at G5. T4 is third-party and unread, and is never installed.
<!-- END DEMIURGE BRIEF GIST -->
