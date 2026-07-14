"""World-model Surprise (issue #6): per-infant forecaster + LOIO validation.

The learned half of Tier 2. A per-infant linear forecaster (no shared population
weights) produces a per-window Surprise = negative log-likelihood of the next window
under the infant's own fitted model. See docs/research/world-model-surprise-validation.md.
"""
