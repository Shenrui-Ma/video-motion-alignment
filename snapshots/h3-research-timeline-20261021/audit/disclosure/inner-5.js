
  (() => {
    for (const root of document.querySelectorAll(".viz-carousel")) {
      const panels = Array.from(
        root.querySelectorAll(":scope > [data-variant]"),
      );
      if (panels.length === 0) {
        continue;
      }
      root.setAttribute("role", "group");
      panels.forEach((panel, index) => {
        panel.hidden = index !== 0;
        panel.setAttribute("role", "group");
        if (!panel.hasAttribute("aria-label")) {
          panel.setAttribute("aria-label", panel.dataset.variant);
        }
      });
      root.dataset.activeVariant = panels[0].dataset.variant;
      if (panels.length === 1) {
        continue;
      }

      const controls = document.createElement("div");
      controls.className = "viz-carousel-controls";
      // Portable copy of the settings dropdown's legacy glyph; no 14px icon-package preset matches it.
      // https://github.com/openai/openai/blob/master/codex/codex-apps/webview/src/icons/chevron.svg
      controls.innerHTML = `
      <button type="button" class="viz-carousel-previous cursor-interaction"><i data-lucide="chevron-left" aria-hidden="true"></i></button>
      <details class="viz-carousel-picker">
        <summary class="cursor-interaction">
          <span class="viz-carousel-count tabular-nums"></span>
          <span class="viz-carousel-name"></span>
          <svg class="viz-carousel-caret" width="14" height="14" viewBox="0 0 20 21" fill="none" aria-hidden="true" focusable="false">
            <path d="M15.2793 7.71101C15.539 7.45131 15.961 7.45131 16.2207 7.71101C16.4804 7.97071 16.4804 8.39272 16.2207 8.65242L10.4707 14.4024C10.211 14.6621 9.78902 14.6621 9.52932 14.4024L3.77932 8.65242L3.69436 8.54792C3.52385 8.28979 3.55205 7.93828 3.77932 7.71101C4.00659 7.48374 4.3581 7.45554 4.61623 7.62605L4.72073 7.71101L10 12.9903L15.2793 7.71101Z" fill="currentColor" stroke="currentColor" stroke-width="0.6" />
          </svg>
        </summary>
        <div class="viz-carousel-options"></div>
      </details>
      <button type="button" class="viz-carousel-next cursor-interaction"><i data-lucide="chevron-right" aria-hidden="true"></i></button>`;
      const previous = controls.querySelector(".viz-carousel-previous");
      const next = controls.querySelector(".viz-carousel-next");
      const picker = controls.querySelector(".viz-carousel-picker");
      const summary = picker.querySelector("summary");
      const count = controls.querySelector(".viz-carousel-count");
      const name = controls.querySelector(".viz-carousel-name");
      const options = controls.querySelector(".viz-carousel-options");
      const status = document.createElement("span");
      status.className = "sr-only";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      status.setAttribute("aria-atomic", "true");
      previous.setAttribute(
        "aria-label",
        root.dataset.previousLabel ?? "Previous variant",
      );
      next.setAttribute("aria-label", root.dataset.nextLabel ?? "Next variant");

      let active = 0;
      let mousePointerId = null;
      let summaryPointerHandled = false;
      summary.addEventListener("pointerdown", (event) => {
        summaryPointerHandled =
          event.pointerType === "mouse" && event.button === 0 && !event.ctrlKey;
        if (!summaryPointerHandled) {
          return;
        }
        event.preventDefault();
        summary.focus({ preventScroll: true });
        picker.open = !picker.open;
        mousePointerId = picker.open ? event.pointerId : null;
      });
      summary.addEventListener("click", (event) => {
        if (summaryPointerHandled && event.detail > 0) {
          event.preventDefault();
        }
      });
      const choices = panels.map((panel, index) => {
        const choice = document.createElement("button");
        choice.type = "button";
        choice.className = "cursor-interaction";
        choice.textContent = panel.dataset.variant;
        choice.addEventListener("click", () => {
          select(index);
          summary.focus();
        });
        choice.addEventListener("pointerup", (event) => {
          if (
            picker.open &&
            event.pointerType === "mouse" &&
            event.button === 0 &&
            event.pointerId === mousePointerId
          ) {
            choice.click();
          }
        });
        options.appendChild(choice);
        return choice;
      });
      const select = (index) => {
        const changed = active !== index;
        active = index;
        panels.forEach((panel, position) => {
          panel.hidden = position !== active;
          choices[position].setAttribute(
            "aria-current",
            String(position === active),
          );
        });
        root.dataset.activeVariant = panels[active].dataset.variant;
        count.textContent = `${active + 1} / ${panels.length}`;
        name.textContent = panels[active].dataset.variant;
        picker.open = false;
        mousePointerId = null;
        if (changed) {
          status.textContent = `${count.textContent}: ${name.textContent}`;
        }
      };
      previous.addEventListener("click", () =>
        select((active + panels.length - 1) % panels.length),
      );
      next.addEventListener("click", () =>
        select((active + 1) % panels.length),
      );
      picker.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && picker.open) {
          event.preventDefault();
          picker.open = false;
          mousePointerId = null;
          summary.focus();
          return;
        }
        if (event.altKey || event.ctrlKey || event.metaKey) {
          return;
        }
        const index = choices.indexOf(document.activeElement);
        let nextIndex;
        if (event.key === "ArrowDown") {
          nextIndex = index < 0 ? active : (index + 1) % choices.length;
        } else if (event.key === "ArrowUp") {
          nextIndex = index < 0 ? active : (index + choices.length - 1) % choices.length;
        } else if (picker.open && event.key === "Home") {
          nextIndex = 0;
        } else if (picker.open && event.key === "End") {
          nextIndex = choices.length - 1;
        } else {
          return;
        }
        event.preventDefault();
        picker.open = true;
        choices[nextIndex].focus();
      });
      picker.addEventListener("focusout", (event) => {
        if (!picker.contains(event.relatedTarget)) {
          picker.open = false;
          mousePointerId = null;
        }
      });
      const dismiss = (event) => {
        if (!summary.contains(event.target)) {
          mousePointerId = null;
        }
        if (!picker.contains(event.target)) {
          picker.open = false;
        }
      };
      const endPointerSelection = () => {
        mousePointerId = null;
      };
      const sizePicker = () => {
        root.style.setProperty(
          "--viz-carousel-picker-height",
          `${picker.open ? options.offsetHeight : 0}px`,
        );
      };
      picker.addEventListener("toggle", sizePicker);
      window.addEventListener("resize", sizePicker);
      document.addEventListener("pointerdown", dismiss);
      document.addEventListener("pointerup", endPointerSelection);
      document.addEventListener("pointercancel", endPointerSelection);
      window.addEventListener("blur", endPointerSelection);
      window.addEventListener(
        "pagehide",
        () => {
          document.removeEventListener("pointerdown", dismiss);
          document.removeEventListener("pointerup", endPointerSelection);
          document.removeEventListener("pointercancel", endPointerSelection);
          window.removeEventListener("blur", endPointerSelection);
          window.removeEventListener("resize", sizePicker);
        },
        { once: true },
      );
      root.append(controls, status);
      select(0);
    }
  })();
