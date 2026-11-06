
# FasalBima Sathi - Interactive Menu

# Sample crop list
crops = ["Soybean", "Cotton", "Rice", "Wheat"]

while True:

    print("\n================================")
    print("       FASALBIMA SATHI")
    print("================================")
    print("1. About the Project")
    print("2. View Supported Sample Crops")
    print("3. Check Sample Crop Information")
    print("0. Exit")
    print("================================")

    choice = input("Enter your choice: ")

    # Option 1: About the project
    if choice == "1":
        print("\nFasalBima Sathi")
        print("An AI-powered PMFBY information assistant.")
        print("It helps farmers understand crop insurance.")

    # Option 2: Display crops using a for loop
    elif choice == "2":
        print("\nSample Crops:")

        for crop in crops:
            print("-", crop)

    # Option 3: Sample crop information
    elif choice == "3":
        selected_crop = input("Enter your crop name: ").strip().lower()

        if selected_crop in [crop.lower() for
         crop in crops]:
            print(f"{selected_crop.title()} is in our sample crop list.")
            print("Actual PMFBY eligibility depends on notified")
            print("crop, location, season and applicable rules.")
        else:
            print("Crop not found in our sample list.")

    # Option 0: Exit
    elif choice == "0":
        print("\nThank you for using FasalBima Sathi!")
        break

    # Invalid choice
    else:
        print("Invalid choice. Please try again.")
