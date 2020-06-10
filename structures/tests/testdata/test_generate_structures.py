from random import randrange


def get_random_subset(lst: list, max_members: int) -> list:
    lst2 = lst.copy()
    subset = list()
    max_members = min(max_members, len(lst))

    for x in range(randrange(max_members) + 1):
        m = lst2.pop(randrange(len(lst2)))
        subset.append(m)

    return subset


my_list = ["one", "two", "three", "four"]

subset = get_random_subset(my_list, 4)
# print(subset)
