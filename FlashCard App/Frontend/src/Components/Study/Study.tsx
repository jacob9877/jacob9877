import { useState, useEffect } from "react";
import "./Study.css";
import arrow_icon from "../Assets/arrow.png";

function Study() {
  const [cards, setCards] = useState<any[]>([]);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  const CardID = localStorage.getItem("card_id");

  const app_name = "cop4331-project.online";
  function buildPath(route: string): string {
    if (process.env.NODE_ENV !== "development") {
      return "http://" + app_name + ":5000/" + route;
    } else {
      return "http://localhost:5000/" + route;
    }
  }

  async function fetchCards() {
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
    } catch (error: any) {
      alert(error.toString());
    }
  }

  useEffect(() => {
    fetchCards();
  }, []);

  const flipCard = () => {
    setIsFlipped(!isFlipped);
  };

  const nextCard = () => {
    if (currentCardIndex < cards.length - 1) {
      setCurrentCardIndex(currentCardIndex + 1);
      setIsFlipped(false);
    }
  };

  const prevCard = () => {
    if (currentCardIndex > 0) {
      setCurrentCardIndex(currentCardIndex - 1);
      setIsFlipped(false);
    }
  };

  const backToMenu = () => {
    window.location.href = "/menu";
  };

  return (
    <div className="Study">
      <div className="topButtons">
        <img
          src={arrow_icon}
          id="backMenu"
          onClick={backToMenu}
          alt="Back to menu"
        />
      </div>

      {cards.length > 0 && (
        <div className="flashcard-container">
          <div
            className={`flashcard ${isFlipped ? "flipped" : ""}`}
            onClick={flipCard}
          >
            <div className="flashcard-inner">
              <div className="flashcard-front">
                <p>{cards[currentCardIndex].Term}</p>
              </div>
              <div className="flashcard-back">
                <p>{cards[currentCardIndex].Definition}</p>
              </div>
            </div>
          </div>
          <div className="navigation-buttons">
            <button onClick={prevCard} disabled={currentCardIndex === 0}>
              Previous
            </button>
            <button
              onClick={nextCard}
              disabled={currentCardIndex === cards.length - 1}
            >
              Next
            </button>
          </div>
          <p className="card-counter">
            {currentCardIndex + 1} / {cards.length}
          </p>
        </div>
      )}
    </div>
  );
}

export default Study;
