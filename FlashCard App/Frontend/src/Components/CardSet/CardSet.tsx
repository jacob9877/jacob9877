import { useState, useEffect } from "react";
import "./CardSet.css";
import arrow_icon from "../Assets/arrow.png";
import pen_icon from "../Assets/edit.png";
import x_icon from "../Assets/x.png";
import study_icon from "../Assets/study.png";

function CardSet() {
  let CardID = localStorage.getItem("card_id");
  console.log("CardID: " + CardID);

  const [cards, setCards] = useState<any[]>([]);
  const [state, setState] = useState("normal");
  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [editingCards, setEditingCards] = useState<{ [key: string]: boolean }>(
    {}
  );
  const [editQuestion, setEditQuestion] = useState("");
  const [editAnswer, setEditAnswer] = useState("");

  // const [isFadingOut, setIsFadingOut] = useState(false);
  // const cardSetId = localStorage.getItem("card_set_id");

  const app_name = "cop4331-project.online";
  function buildPath(route: string): string {
    if (process.env.NODE_ENV != "development") {
      return "http://" + app_name + ":5000/" + route;
    } else {
      return "http://localhost:5000/" + route;
    }
  }

  function backToMenu() {
    window.location.href = "/menu";
  }

  async function studySet() {
    console.log("Opening Set: " + CardID);
    localStorage.setItem("card_id", CardID as string);
    window.location.href = "/study";
  }

  async function showCards(): Promise<void> {
    if (!CardID) {
      console.error("Card set ID is missing");
      return;
    }

    let obj = { id: CardID };
    let js = JSON.stringify(obj);

    try {
      const response = await fetch(buildPath("api/getCard"), {
        method: "POST",
        body: js,
        headers: { "Content-Type": "application/json" },
      });

      const resText = await response.text();
      if (!resText) {
        console.error("Empty response received from the server");
        return;
      }

      let res = JSON.parse(resText);

      if (!res.results || !Array.isArray(res.results)) {
        console.error("Expected 'cards' array not found in response", res);
        return;
      }

      setCards(res.results);
      console.log(cards);
    } catch (error: any) {
      alert(error.toString());
    }
  }

  async function deleteCard(id: string) {
    let text = "Are you sure you want to delete?";
    if (confirm(text) == true) {
    let obj = { id: id };
    let js = JSON.stringify(obj);
    try {
      const response = await fetch(buildPath("api/deleteCard"), {
        method: "POST",
        body: js,
        headers: { "Content-Type": "application/json" },
      });

      const resText = await response.text();
      if (!resText) {
        console.error("Empty response received from the server");
        return;
      }
      console.log("CardID:" + id + " deleted");
      showCards();
    } catch (error: any) {
      alert(error.toString());
    }
  }
  }

  function toggleEdit(cardId: string) {
    setEditingCards((prev) => ({
      ...prev,
      [cardId]: !prev[cardId],
    }));
    setEditQuestion(cards.find((card) => card._id === cardId)?.Term || "");
    setEditAnswer(cards.find((card) => card._id === cardId)?.Definition || "");
  }

  async function editCard(id: string) {

    let obj = { id: id, question: editQuestion, answer: editAnswer };
    let js = JSON.stringify(obj);
    try {
      const response = await fetch(buildPath("api/updateCard"), {
        method: "POST",
        body: js,
        headers: { "Content-Type": "application/json" },
      });

      const resText = await response.text();
      if (!resText) {
        console.error("Empty response received from the server");
        return;
      }
      console.log("Card updated");
      showCards();
      toggleEdit(id);
    } catch (error: any) {
      alert(error.toString());
    }
  }

  async function addCard(event: any): Promise<void> {
    event.preventDefault();
    let obj = {
      Term: newQuestion,
      Definition: newAnswer,
      setID: CardID,
    };
    let js = JSON.stringify(obj);
    try {
      const response = await fetch(buildPath("api/createCard"), {
        method: "POST",
        body: js,
        headers: { "Content-Type": "application/json" },
      });

      const resText = await response.text();
      if (!resText) {
        console.error("Empty response received from the server");
        return;
      }
      console.log("Card added");
      setState("normal");
      showCards();
    } catch (error: any) {
      alert(error.toString());
    }
  }

  function addCardWrapper(): void {
    if (state === "adding") {
      // setIsFadingOut(true);
      setTimeout(() => {
        setState("normal");
        // setIsFadingOut(false);
      }, 150);
    } else {
      setState("adding");
    }
  }

  function handleNewQuestion(event: any): void {
    setNewQuestion(event.target.value);
  }

  function handleNewAnswer(event: any): void {
    setNewAnswer(event.target.value);
  }

  useEffect(() => {
    showCards();
  }, []);

  return (
    <div className="CardSet">
      <div className="blurredBackground"></div>
      <div className="topButtons">
        <img
          src={arrow_icon}
          id="backMenu"
          onClick={backToMenu}
          alt="Back to menu"
        />
        <div className="rightButtons">
          <div className="circleButton addButton" onClick={addCardWrapper}>
            +
          </div>
          <div className="circleButton studyButton" onClick={studySet}>
            <img src={study_icon} alt="Study icon" />
          </div>
        </div>
      </div>

      <div>
        <h1>Card Set</h1>
      </div>
      <div>
        <h2>Cards In This Set</h2>
      </div>
      {state === "normal" ? (
        <div></div>
      ) : (
        <form onSubmit={addCard} className="addCardForm">
          <input
            type="text"
            id="cardQuestion"
            placeholder="Question"
            onChange={handleNewQuestion}
          />
          <input
            type="text"
            id="cardAnswer"
            placeholder="Answer"
            onChange={handleNewAnswer}
          />
          <button type="submit" className="makeCard">
            Add
          </button>
        </form>
      )}

      <div className="listCards">
        {cards.map((card, index) => (
          <div
            key={index}
            className={`card ${editingCards[card._id] ? "editing" : ""}`}
            id={`card${index + 1}`}
          >
            <div className="card-content">
              <div className="questionAnswer">
                <div className="term">
                  <strong>Q: </strong>
                  {card.Term}
                </div>
                <strong>A: </strong>
                {card.Definition}
              </div>
              <div className="editDelete2">
                <img
                  src={pen_icon}
                  onClick={() => toggleEdit(card._id)}
                  alt="Edit icon"
                  id="editCardButton"
                />
                <img
                  src={x_icon}
                  onClick={() => deleteCard(card._id)}
                  alt="Delete icon"
                  id="delCardButton"
                />
              </div>
            </div>
            {editingCards[card._id] && (
              <div className="editForm">
                <input
                  type="text"
                  value={editQuestion}
                  onChange={(e) => setEditQuestion(e.target.value)}
                  placeholder="Edit Question"
                />
                <input
                  type="text"
                  value={editAnswer}
                  onChange={(e) => setEditAnswer(e.target.value)}
                  placeholder="Edit Answer"
                />
                <button onClick={() => editCard(card._id)}>Save</button>
                <button onClick={() => toggleEdit(card._id)}>Cancel</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default CardSet;
