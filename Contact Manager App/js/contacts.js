function getContacts() {
  fetch("http://cop4331-project.online/LAMPAPI/GetContacts.php", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ userId: localStorage.getItem("userId") }),
  })
    .then((response) => response.json())
    .then((data) => {
      displayContacts(data.results);
    })
    .catch((error) => {
      console.error("Error fetching contacts:", error);
    });
}

function searchContacts() {
  let userId = localStorage.getItem("userId");
  let searchTerm = document.getElementById("search-input").value;
  if (searchTerm.trim() === "") {
    getContacts();
  } else {
    fetch(`http://cop4331-project.online/LAMPAPI/SearchContact.php`, {
      method: "POST",
      body: JSON.stringify({ userId, query: searchTerm }),
    })
      .then((response) => response.json())
      .then((data) => {
        displayContacts(data.results);
      })
      .catch((error) => {
        console.error("Error searching contacts:", error);
      });
  }
}

function setupSearchListener() {
  const searchInput = document.getElementById("search-input");
  searchInput.addEventListener("input", function () {
    searchContacts();
  });
}

function displayContacts(contacts) {
  const contactList = document.querySelector(".contact-list");
  contactList.innerHTML = "";

  contacts.forEach((contact) => {
    const contactItem = document.createElement("div");
    contactItem.className = "contact-item";
    contactItem.innerHTML = `
        <div class="contact-text">
          <h3>${contact.Name}</h3>
          <p>${contact.Email}</p>
        </div>
        <button class="contact-item-button delete-button" data-id="${contact.ID}">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="contact-item-button-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
          </svg>
        </button>
      `;
    contactItem.addEventListener("click", () => displayContactDetails(contact));
    contactList.appendChild(contactItem);
  });

  document.querySelectorAll(".delete-button").forEach((button) => {
    button.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteContact(button.dataset.id);
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  getContacts();
  setupSearchListener();
});

function displayContactDetails(contact) {
  const contactDetails = document.querySelector(".contact-details");
  contactDetails.innerHTML = `
    <div class="contact-details-header">
      <div class="contact-details-header-title">
        <p>Your Contacts</p>
        <h3>${contact.Name}</h3>
      </div>
      <div class="contact-details-header-buttons">
        <button class="contact-details-button edit-button" data-contact='${JSON.stringify(
          contact
        )}'>
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="contact-details-button-icon">
          <path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
        </svg>      
        </button>
      </div>
    </div>
    <div class="contact-details-body">
      <div class="contact-details-item">
        <h3>Full Name</h3>
        <p>${contact.Name}</p>
      </div>
      <div class="contact-details-item">
        <h3>Phone</h3>
        <p>${contact.Phone}</p>
      </div>
      <div class="contact-details-item">
        <h3>Email</h3>
        <p>${contact.Email}</p>
      </div>
      <div class="contact-details-item">
        <h3>Date Created</h3>
        <p>${contact.DateCreated}</p>
      </div>
    </div>
  `;

  document.querySelector(".edit-button").addEventListener("click", function () {
    editContact(JSON.parse(this.dataset.contact));
  });

  document
    .querySelector(".delete-button")
    .addEventListener("click", function (e) {
      e.stopPropagation();
      deleteContact(this.dataset.id);
    });
}

function displayContactDetailsEmpty() {
  const contactDetails = document.querySelector(".contact-details");
  contactDetails.innerHTML = `
    <div class="contact-image-container">
      <img src="empty.png" class="contact-image" />
      <h2>Select a Contact from the Sidebar</h2>
    </div>`;
}

function deleteContact(contactId) {
  if (confirm("Are you sure that you want to delete this contact?") == true) {
    fetch(
      `http://cop4331-project.online/LAMPAPI/DeleteContact.php?id=${contactId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    )
      .then((response) => response.json())
      .then((data) => {
        displayContactDetailsEmpty();
        getContacts();
      })
      .catch((error) => {
        console.error("Error deleting contact:", error);
      });
  } else {
    return;
  }
}

function buildContact() {
  const contactDetails = document.querySelector(".contact-details");

  contactDetails.innerHTML = `
    <div class="contact-details-header">
      <div class="contact-details-header-title">
        <p>Contacts</p>
        <h3>Create Contact</h3>
      </div>
      <div class="contact-details-header-buttons">
        <button class="contact-details-button save-button">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="contact-details-button-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        </button>
        <button class="contact-item-button cancel-button"">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="contact-item-button-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
    <div class="contact-details-body">
      <div class="contact-details-item">
        <h3>Full Name</h3>
        <input type="text" id="create-name" />
      </div>
      <div class="contact-details-item">
        <h3>Phone</h3>
        <input type="text" id="create-phone" />
      </div>
      <div class="contact-details-item">
        <h3>Email</h3>
        <input type="text" id="create-email" />
      </div>

    </div>
  `;

  document.querySelector(".save-button").addEventListener("click", function () {
    const name = document.getElementById("create-name").value;
    const phone = document.getElementById("create-phone").value;
    const email = document.getElementById("create-email").value;
    const dateCreated = new Date().toLocaleDateString();

    addContact(
      parseInt(localStorage.getItem("userId")),
      name,
      phone,
      email,
      dateCreated
    );
  });

  document
    .querySelector(".cancel-button")
    .addEventListener("click", function () {
      cancelEdit(this.dataset.ID);
    });
}

function addContact(userId, name, phone, email, dateCreated) {
  fetch(`http://cop4331-project.online/LAMPAPI/CreateContact.php`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ userId, name, phone, email }),
  })
    .then((response) => response.json())
    .then((data) => {
      displayContactDetails({
        ID: data.id,
        Name: name,
        Phone: phone,
        Email: email,
        DateCreated: dateCreated,
      });
      getContacts();
    })
    .catch((error) => {
      console.error("Error adding contact:", error);
    });
}

function editContact(contact) {
  const contactDetails = document.querySelector(".contact-details");

  contactDetails.innerHTML = `
    <div class="contact-details-header">
      <div class="contact-details-header-title">
        <p>Edit Contact</p>
        <h3>${contact.Name}</h3>
      </div>
      <div class="contact-details-header-buttons">
        <button class="contact-details-button save-button" data-id="${contact.ID}">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="contact-details-button-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        </button>
        <button class="contact-item-button cancel-button" data-id="${contact.ID}">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="contact-item-button-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
    <div class="contact-details-body">
      <div class="contact-details-item">
        <h3>Full Name</h3>
        <input type="text" id="edit-name" value="${contact.Name}" />
      </div>
      <div class="contact-details-item">
        <h3>Phone</h3>
        <input type="text" id="edit-phone" value="${contact.Phone}" />
      </div>
      <div class="contact-details-item">
        <h3>Email</h3>
        <input type="text" id="edit-email" value="${contact.Email}" />
      </div>
      <div class="contact-details-item-hidden">
        <h3>Date Created</h3>
        <input type="text" id="edit-date" value="${contact.DateCreated}" />
      </div>
    </div>
  `;

  document.querySelector(".save-button").addEventListener("click", function () {
    saveContact(contact.ID);
  });

  document
    .querySelector(".cancel-button")
    .addEventListener("click", function () {
      cancelEdit(this.dataset.ID);
    });
}

function saveContact(contactId) {
  const name = document.getElementById("edit-name").value;
  const phone = document.getElementById("edit-phone").value;
  const email = document.getElementById("edit-email").value;
  const dateCreated = document.getElementById("edit-date").value;

  fetch(
    `http://cop4331-project.online/LAMPAPI/UpdateContact.php?id=${contactId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name, phone, email }),
    }
  )
    .then((response) => response.json())
    .then((data) => {
      getContacts();
      displayContactDetails({
        ID: contactId,
        Name: name,
        Phone: phone,
        Email: email,
        DateCreated: dateCreated,
      });
    })
    .catch((error) => {
      console.error("Error saving contact:", error);
    });
}

function cancelEdit(contactId) {
  fetch(`http://cop4331-project.online/LAMPAPI/GetContacts.php`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ userId: window.localStorage.getItem("userId") }),
  })
    .then((response) => response.json())
    .then((data) => {
      const contact = data.results.find((c) => c.ID === contactId);
      if (contact) {
        displayContactDetails(contact);
      } else {
        displayContactDetailsEmpty();
      }
    })
    .catch((error) => {
      console.error("Error cancelling edit:", error);
    });
}

function signOut() {
  localStorage.removeItem("userId");
  window.location.href = "index.html";
}
