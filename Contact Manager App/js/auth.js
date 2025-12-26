document.addEventListener("DOMContentLoaded", function () {
  const loginForm = document.getElementById("loginForm");
  const errorMessage = document.getElementById("errorMessage");

  loginForm.addEventListener("submit", function (e) {
    e.preventDefault();

    const login = document.getElementById("login").value;
    const password = document.getElementById("password").value;

    fetch("http://cop4331-project.online/LAMPAPI/Login.php", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ login, password }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          errorMessage.textContent = data.error;
          errorMessage.style.display = "block";
        } else {
          localStorage.setItem("userId", data.id);
          window.location.href = "contacts.html";
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        errorMessage.textContent = "An error occurred. Please try again.";
        errorMessage.style.display = "block";
      });
  });
});
