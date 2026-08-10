document.addEventListener("DOMContentLoaded", () => {
    const alerts = document.querySelectorAll(".flash");
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.classList.add("hide");
        }, 4500);
    });

    document.querySelectorAll("[data-confirm]").forEach((button) => {
        button.addEventListener("click", (event) => {
            if (!confirm(button.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });
});
