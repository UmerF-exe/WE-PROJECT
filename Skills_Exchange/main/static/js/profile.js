document.addEventListener("DOMContentLoaded", () => {
    const nextBtns = document.querySelectorAll(".next-step");
    const prevBtns = document.querySelectorAll(".prev-step");
    const steps = document.querySelectorAll(".form-section");
    const progressSteps = document.querySelectorAll(".progress-step");

    function showStep(stepNum) {
        steps.forEach((section) => section.classList.remove("active"));
        const target = document.getElementById(`step-${stepNum}`);
        if (target) target.classList.add("active");

        progressSteps.forEach((p) => p.classList.remove("active"));
        const currentStep = document.querySelector(`.progress-step[data-step="${stepNum}"]`);
        if (currentStep) currentStep.classList.add("active");
    }

    nextBtns.forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const next = btn.getAttribute("data-next");
            showStep(next);
        });
    });

    prevBtns.forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const prev = btn.getAttribute("data-prev");
            showStep(prev);
        });
    });
});
