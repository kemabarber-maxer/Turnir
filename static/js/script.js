// ==========================
// PAGE ANIMATION
// ==========================


document.addEventListener(
    "DOMContentLoaded",
    function(){


        const cards =
        document.querySelectorAll(
            ".card, .form-card, .profile-card"
        );


        cards.forEach(
            function(card,index){


                card.style.animationDelay =
                (index * 0.1)+"s";


            }
        );


    }
);




// ==========================
// COPY TEXT
// ==========================


function copyText(text){


    navigator.clipboard.writeText(
        text
    );


    alert(
        "Göçürildi ✅"
    );

}




// ==========================
// CONFIRM
// ==========================


function confirmDelete(){


    return confirm(
        "Dowam etmek isleýärsiňizmi?"
    );


}
