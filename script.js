let students = JSON.parse(localStorage.getItem("students")) || [];

function displayStudents() {
    const table = document.getElementById("studentTable");
    table.innerHTML = "";

    students.forEach((student, index) => {
        table.innerHTML += `
        <tr>
            <td>${student.name}</td>
            <td>${student.roll}</td>
            <td>${student.email}</td>
            <td>${student.course}</td>
            <td>${student.year}</td>
            <td>
                <button onclick="deleteStudent(${index})">Delete</button>
            </td>
        </tr>
        `;
    });

    localStorage.setItem("students", JSON.stringify(students));
}

function addStudent() {
    const name = document.getElementById("name").value;
    const roll = document.getElementById("roll").value;
    const email = document.getElementById("email").value;
    const course = document.getElementById("course").value;
    const year = document.getElementById("year").value;

    if (!name || !roll || !email || !course || !year) {
        alert("Please fill all fields");
        return;
    }

    students.push({ name, roll, email, course, year });
    displayStudents();

    document.querySelectorAll("input").forEach(input => input.value = "");
}

function deleteStudent(index) {
    students.splice(index, 1);
    displayStudents();
}

function searchStudent() {
    const search = document.getElementById("search").value.toLowerCase();
    const rows = document.querySelectorAll("#studentTable tr");

    rows.forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(search)
            ? ""
            : "none";
    });
}

displayStudents();
