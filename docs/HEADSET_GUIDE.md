# Helm headset: print and assembly guide

## 1. What to upload (5 files, one copy each)

| File | What it is | Size (mm) |
|---|---|---|
| `1_headband.stl` | the band over the head | 168 × 103 × 14 |
| `2_ear_plate_left.stl` | left ear plate: holds the UNO Q, has the boom hinge tab | 95 × 104 × 11 |
| `3_ear_plate_right.stl` | right ear plate | 80 × 104 × 11 |
| `4_boom.stl` | hinged arm from the left plate toward the mouth | 85 × 56 × 5 |
| `5_sensor_arm.stl` | clamps onto the boom, carries the sensor under the mouth | 118 × 32 × 14 |

Everything fits on any common printer (largest part 168 mm). Every part prints **flat, exactly as
oriented in the file, with no supports**.

## 2. Print settings (put these in the form's notes)

- **Material:** PLA is fine. PETG is better for the headband if they have it, because it flexes.
- **Layers and infill:** 0.2 mm layers, 3 walls, 20% infill.
- **Headband:** 4 walls and 30% infill. It's a spring, and the extra walls stop it cracking.
- **No supports, no brim.**

**Time, roughly:** about 4–5 hours total on a fast printer (Bambu Lab, Prusa MK4), or about
8–10 hours on an older one (Ender 3, Prusa MK3). The two ear plates are about two-thirds of that.
Parts on separate printers print in parallel.

## 3. Hardware (any M3 screw kit; the hardware table usually has these)

| Item | Qty | Where | No-screw fallback |
|---|---|---|---|
| M3 × 12 bolt + M3 nut | 1 | boom hinge | none: this one really wants a bolt |
| M3 × 20 bolt + M3 nut | 1 | sensor arm to boom | 3 mm wooden skewer piece + tape |
| M3 × 10 screw | 2 | headband height locks | 3 mm wooden skewer pieces |
| M3 × 8 screw | 4 | UNO Q to its posts (optional) | zip ties through the side slots |
| small zip ties | 6–8 | sensor, wires, USB cable | tape |
| foam, felt or a few layers of tape | – | inside of both ear plates, for comfort | – |

## 4. Assembly

**Which plate is which:** the **left** plate has four posts and a round tab sticking out of one
corner. On the head, that tab goes **toward the face, at the bottom**. On both plates, the raised
block with the slot faces **outward**, away from the head.

1. **Headband into the plates.** Slide each end of the band down into the slot in the raised block
   at the top of each plate.
2. **Set the height.** Each band end has 4 holes. Line one up with the hole on top of the block and
   drive an M3 × 10 screw in, or push in a piece of skewer. Use the **same hole number on both
   sides**. Start with the 3rd hole from the top; use a higher hole for a smaller head, a lower one
   for a bigger head.
3. **Boom hinge.**
   - Press an M3 nut into the hex pocket on the **inside** (head side) of the left plate's tab.
   - Put the round end of the boom on the **outside** of the tab.
   - Push the M3 × 12 bolt through the boom and the tab into the nut.
   - Tighten until the boom holds its angle on its own but still moves by hand.
   - The boom should curve **down and forward** toward the mouth. If it points up or back, flip it
     over.
4. **Sensor arm.** Slide the straight tip of the boom through the slot in the sensor arm's block.
   Line up the holes and fit the M3 × 20 bolt and nut. The long bar should point **inward, toward
   the middle of the face**, with the flat platform underneath.
5. **Sensor.**
   - Lay the sensor board flat on the platform and zip-tie it through the four slots.
   - The two nozzles point **up**.
   - Push a **bendy straw** onto the nozzle that made the number go **up** when you puffed.
6. **UNO Q.**
   - Set it on the four posts on the left plate's outside face: LED grid facing out, USB-C toward
     the face, and the 5V / GND / A0–A5 header along the **bottom**.
   - Screw it down with M3 × 8 screws, or zip-tie it through the side slots.
   - The posts are at the standard UNO mounting-hole positions. If a hole doesn't line up exactly,
     skip the screws: the posts still hold the board off the plate, and zip ties hold it down.
7. **Wires.** Run the sensor's three wires along the sensor arm and boom to the board and zip-tie
   them along the way. Keep the taped resistor joints near the board. Wiring is unchanged from
   before: 5V, GND, and Analog through the two resistors into A2.
8. **USB cable.** Make a loop and zip-tie it through one of the side slots before it leaves the
   headset, so a tug pulls the headset and not the board's port.
9. **Comfort.** Stick foam or felt (or a few layers of tape) on the inside of both ear plates.
10. **Fit it on someone.**
    - Swing the boom up or down until the end of the bendy straw sits at the lips.
    - The sensor ends up about 2 cm below and 2–3 cm in front of the mouth; the straw's bend
      covers the rest.
    - Check that the camera still sees the mouth.

## 5. Notes

- **The band clamps on purpose.** It's printed slightly narrower than a head and springs open when
  worn, which holds the headset on. Don't pull it open more than a couple of centimetres per side
  when it's off the head, especially in PLA.
- **Fit range:** the four height settings cover roughly the normal adult range, and the band's
  flex covers different head widths.
- **What I checked before sending:**
  - Every file is a single, watertight solid that sits flat on the bed.
  - The band end fits its slot with 0.2 mm clearance per side, at all four height settings, and
    never slides down into the board.
  - The hinge bolt ends flush on the head side.
  - The sensor arm clears the face by about 2 cm.
  - None of the parts overlap when assembled.
