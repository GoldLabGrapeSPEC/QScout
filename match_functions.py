from random import random
import math
import numpy as np

# offset rate algorithms
def rate_offset_match_gradients(context, target, compare):
    """
    the most ambitious of my comparison algorithms. attempts to compare the... for lack of a better word,
    derivitives of the two samples.
    """
    clip = np.s_[:, :, :]
    # it's highly unlikely that two samples with the same shape but different margins will be compared
    if target.shape() != compare.shape():
        t_m, c_m = context.calc_margins(target, compare)
    else:
        t_m = c_m = np.s_[:, :, :]
    a1 = target.gradients(t_m)
    a2 = compare.gradients(c_m)
    if a1.shape != a2.shape:
        # if off-by-one error, just clip a bit and move on with your life
        if np.all(np.abs(np.array(a1.shape) - np.array(a2.shape)) <= 1):
            min_margins = np.minimum(a1.shape, a2.shape)
            clip = np.s_[0:min_margins[0] - 1, 0:min_margins[1] - 1, ...]
        else:
            return 0

    return 1.0 - (np.mean(np.abs(a1[clip] - a2[clip])) / 255)


def rate_offset_match_relative_match_count(context, target, compare):
    t_m, c_m, clip = context.calc_margins_clip(target, compare)
    if clip is None:
        return 0

    diff_threshold = 0.1  # arbitarary number!
    diff = target.norm(t_m)[clip] - compare.norm(c_m)[clip]
    match = diff[diff < diff_threshold]
    rating = 1.0 - (np.count_nonzero(match) / target.a.size)
    return rating


def rate_offset_match_absolute_difference(context, target, compare):
    """
    takes two matrices of raster data and compares them, rating them by similarity
    Just to be clear I am 100% making this algorithm up.
    @param context instance of QScoutPinAlgorithm
    @param target the matrix to check match with
    @param compare the matrix to check if it matches target
    @return a value from 0 to 1, where 0 is no match and 1 is 100% match
    """
    t_m, c_m, clip = context.calc_margins_clip(target, compare)
    if clip is None:
        return 0

    difference = np.abs(compare.data(c_m)[clip] - target.data(t_m)[clip])
    avg_difference = np.mean(difference) / 255
    rating = 1.0 - avg_difference
    return rating


def rate_offset_match_local_normalized_difference(context, target, compare):
    t_m, c_m, clip = context.calc_margins_clip(target, compare)
    if clip is None:
        return 0
    difference = np.abs(target.norm(t_m)[clip] - compare.norm(c_m)[clip])
    avg_difference = np.mean(difference)
    rating = 1.0 - avg_difference
    return rating


def rate_offset_match_global_normalized_difference(context, target, compare):
    """
    takes two matrices of raster data and compares them, rating them by similarity
    Just to be clear I am 100% making this algorithm up.
    @param context instance of QScoutPinAlgorithm
    @param target the matrix to check match with
    @param compare the matrix to check if it matches target
    @return a value from 0 to 1, where 0 is no match and 1 is 100% match
    """
    t_m, c_m, clip = context.calc_margins_clip(target, compare)
    if clip is None:
        return 0
    difference = np.abs(compare.data(c_m)[clip] - target.data(t_m)[clip])
    norm_diff = np.stack([difference[:, :, n] / (context.band_ranges[n, 1] - context.band_ranges[n, 0])
                          for n
                          in range(difference.shape[2])], axis=-1)
    avg_difference = np.mean(norm_diff)
    rating = 1.0 - avg_difference
    return rating


def rate_offset_match_random(context, target, compare):
    """
    for testing.
    ignores target and compare and returns a random value so that there will be at least one pass rating per
    search. I may have done the math wrong here. does not use parameters but params need to be included for
    compatibility
    """

    return random.random() * (math.pow(context.search_iter_size, 2) / context.overlay_match_min_threshold)


MATCH_FUNCTIONS = {
    "Local Normalized Difference": rate_offset_match_local_normalized_difference,
    "Global Normalized Difference": rate_offset_match_global_normalized_difference,
    "Absolute Difference": rate_offset_match_absolute_difference,
    "Relative Match Count": rate_offset_match_relative_match_count,
    "Gradients": rate_offset_match_gradients,
    "Random": rate_offset_match_random
}

