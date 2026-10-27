
document.addEventListener("DOMContentLoaded", function () {
    const filterButtons = document.querySelectorAll(".filter-btn");
    const fileRows = document.querySelectorAll("tbody tr");

    filterButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const selectedCategory = button.dataset.category;

            fileRows.forEach(function (row) {
                const rowCategory = row.dataset.category;

                if (
                    selectedCategory === "All" ||
                    rowCategory === selectedCategory
                ) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                }
            });

            filterButtons.forEach(function (btn) {
                btn.classList.remove("active");
            });

            button.classList.add("active");
        });
    });
});
