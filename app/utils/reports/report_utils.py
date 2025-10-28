def get_patient_title(
    first_name: str | None, last_name: str | None, name: str | None, id: int
) -> str:
    if first_name and last_name:
        return first_name + " " + last_name
    if name:
        return name
    return f"Patient {id}"
