from typing import List

def str_to_list(s: str) -> List[float]:
    number_strings = s.strip("[]").split()

    # Convert each number string to a float
    numbers_list = [float(num) for num in number_strings]

    return numbers_list


def str_to_list2d(string: str) -> List[List[float]]:
    sublist_strings = string.strip('[]').split('] [')

    # Initialize the 2D list
    list_2d = []

    # Process each sublist string
    for sublist_string in sublist_strings:
        # Split the sublist string by spaces and convert to floats
        sublist = [float(value) for value in sublist_string.split()]
        # Append the sublist to the 2D list
        list_2d.append(sublist)

    return list_2d