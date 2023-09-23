const scroll = new LocomotiveScroll({
    el: document.querySelector('.main'),
    smooth: true
});

function init(){
    gsap.registerPlugin(ScrollTrigger);
    
    // Using Locomotive Scroll from Locomotive https://github.com/locomotivemtl/locomotive-scroll
    
    const locoScroll = new LocomotiveScroll({
      el: document.querySelector(".main"),
      smooth: true
    });
    // each time Locomotive Scroll updates, tell ScrollTrigger to update too (sync positioning)
    locoScroll.on("scroll", ScrollTrigger.update);
    
    // tell ScrollTrigger to use these proxy methods for the ".main" element since Locomotive Scroll is hijacking things
    ScrollTrigger.scrollerProxy(".main", {
      scrollTop(value) {
        return arguments.length ? locoScroll.scrollTo(value, 0, 0) : locoScroll.scroll.instance.scroll.y;
      }, // we don't have to define a scrollLeft because we're only scrolling vertically.
      getBoundingClientRect() {
        return {top: 0, left: 0, width: window.innerWidth, height: window.innerHeight};
      },
      // LocomotiveScroll handles things completely differently on mobile devices - it doesn't even transform the container at all! So to get the correct behavior and avoid jitters, we should pin things with position: fixed on mobile. We sense it by checking to see if there's a transform applied to the container (the LocomotiveScroll-controlled element).
      pinType: document.querySelector(".main").style.transform ? "transform" : "fixed"
    });
    
    // each time the window updates, we should refresh ScrollTrigger and then update LocomotiveScroll. 
    ScrollTrigger.addEventListener("refresh", () => locoScroll.update());
    
    // after everything is set up, refresh() ScrollTrigger and update LocomotiveScroll because padding may have been added for pinning, etc.
    ScrollTrigger.refresh();
    
}
init();

var t = gsap.timeline()

t.to(".page1",{
    y:"100vh",
    scale:0.6,
    duration:0
})

t.to(".page1",{
    y:"30vh",
    duration:1,
    delay:1
})

t.to(".page1",{
    y:0,
    rotate:360,
    scale:1,
    duration:0.8
})
var cover1 = document.querySelector(".page10 .box1")
var cover2 = document.querySelector(".page10 .box2")
var cover3 = document.querySelector(".page10 .box3")
var cover4 = document.querySelector(".page10 .box4")

document.querySelector(".page10 .box1").addEventListener("mousemove",()=>{
  cover2.style.marginLeft = "37%";
  cover3.style.marginLeft = "55.5%";
  cover4.style.marginLeft = "74%";
  cover1.style.backgroundColor = "#b4a899";

})

document.querySelector(".page10 .box1").addEventListener("mouseleave",()=>{
  cover2.style.marginLeft = "18.5%";
  cover3.style.marginLeft = "37%";
  cover4.style.marginLeft = "56%";
  cover1.style.backgroundColor = "#C4BCB2";
})

cover2.addEventListener("mousemove",()=>{
  cover3.style.marginLeft = "55.5%";
  cover4.style.marginLeft = "74%";
  cover2.style.backgroundColor = "#b4a899";
})

cover2.addEventListener("mouseleave",()=>{
  cover3.style.marginLeft = "37%";
  cover4.style.marginLeft = "56%";
  cover2.style.backgroundColor = "#C4BCB2";
})

cover3.addEventListener("mousemove",()=>{
  cover4.style.marginLeft = "74%";
  cover3.style.backgroundColor = "#b4a899";
})

cover3.addEventListener("mouseleave",()=>{
  cover4.style.marginLeft = "56%";
  cover3.style.backgroundColor = "#C4BCB2";
})

cover4.addEventListener("mousemove",()=>{
  cover4.style.backgroundColor = "#b4a899";
})

cover4.addEventListener("mouseleave",()=>{
  cover4.style.backgroundColor = "#C4BCB2";
})