function toggleMenu() {
  const navbar = document.querySelector(".navbar");
  navbar.classList.toggle("active");
}

// Smooth Scrolling
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener("click", function(e) {
      e.preventDefault();
      document.querySelector(this.getAttribute("href")).scrollIntoView({
          behavior: "smooth"
      });

      // Close menu after clicking a link (on mobile)
      document.querySelector(".navbar").classList.remove("active");
  });
});

  var loader = document.getElementById("preloader");
  window.addEventListener("load", function () {
    loader.style.display = "none";
  
  })
  
  // popUp
  const main = document.querySelector('.main');
  const popup = document.querySelector('.popup');
  const close = document.querySelector('.close');
  const click = document.querySelector('.click');
  window.onload = function(){
    setTimeout(() => {
      popup.style.display= "block"
      main.style.filter = "blur(2px)";
    }, 2000);
  }
  
  close.addEventListener('click',() =>{
    popup.style.display="none";
    main.style.filter = "blur(0px)";
  
  })
  
  click.addEventListener('click',() =>{
    popup.style.display="none";
    main.style.filter = "blur(0px)";
  })
  
  
  

  
  
  var form = document.getElementById('form');
  form.addEventListener('submit', function(event){
    event.preventDefault();
  
  alert("Your Form have been submitted sucessfully");
  location.reload(true);
  
  })
  
  document.addEventListener("DOMContentLoaded", function () {
    const button = document.querySelector("a.to-top");

    if (!button) return;

    function handleScroll() {
      if (window.scrollY > 100) {
        button.classList.add("active");
      } else {
        button.classList.remove("active");
      }
    }

    window.addEventListener("scroll", handleScroll);

    button.addEventListener("click", function (event) {
      event.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
