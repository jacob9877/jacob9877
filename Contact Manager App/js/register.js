document.addEventListener("DOMContentLoaded", function () {
  const registerForm = document.getElementById("registerForm");
  const errorMessage = document.createElement("div");
  errorMessage.id = "errorMessage";
  errorMessage.style.display = "none";
  errorMessage.style.color = "red";
  registerForm.appendChild(errorMessage);

  registerForm.addEventListener("submit", function (e) {
    e.preventDefault();

    const firstName = document.getElementById("firstName").value.trim();
    const lastName = document.getElementById("lastName").value.trim();
    const login = document.getElementById("login").value.trim();
    const password = document.getElementById("password").value;
    const password2 = document.getElementById("password2").value;

    if (!firstName || !lastName || !login || !password || !password2) {
      showError("All fields are required.");
      return;
    }

    if (password !== password2) {
      showError("Passwords do not match.");
      return;
    }

    fetch("http://cop4331-project.online/LAMPAPI/CreateUser.php", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ firstName, lastName, login, password }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          showError(data.error);
        } else {
          window.location.assign(
            "http://cop4331-project.online/registerSuccess.html"
          );
        }
      })
      .catch((error) => {
        showError("An error occurred. Please try again later.");
        console.error("Error:", error);
      });
  });

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = "block";
  }
});
