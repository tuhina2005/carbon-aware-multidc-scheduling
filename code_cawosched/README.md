# Modification from CaWoSched

We made two minor adjustments to the original implementation provided via [GitHub](https://github.com/KIT-EAE/CaWoSched).

1. In the constructor, the mapping data structure does not sort the given tasks with respect to their original given order. This is not a correctness issue since the precedence constraints are still enforced by the DAG data structure. However, the local search wants to iterate over the tasks from left to right and uses the mapping data structure for this, so we made this minor adjustment of sorting the tasks. Additionally, the potential start times that are tested are affected by this order. Since our modification is closer to the description in the paper, we made this adjustment. However, this also does not affect the correctness of the algorithms.

2. In the local search implementation, the local search stops as soon as a move of positive gain is found. However, it makes more sense to use the best move found. Hence, we adjusted this by removing one `break` statement. 

In preliminary experiments, both fixes did not yield significant gains nor made performance worse. However, we declare them here for transparency. 