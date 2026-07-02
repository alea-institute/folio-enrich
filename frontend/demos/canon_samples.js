// Canon (Catholic Semantic Canon) demo source texts.
//
// All four are public-domain excerpts (pre-1929 US public domain), chosen to be
// "enrich-heavy" — dense with Canon-ontology concepts (Scripture/persons/places,
// sacraments/doctrine, councils/canon-law, social doctrine) so the enrichment is
// impressive against the Catholic Semantic Canon.
//
//   nativity        — Douay-Rheims (Luke 2 + Matthew 2): Nativity & Adoration of the Magi
//   sacraments      — Baltimore Catechism: the seven sacraments and grace
//   trent_eucharist — Council of Trent, Session XIII (Waterworth tr., 1848): the Eucharist
//   rerum_novarum   — Leo XIII, Rerum Novarum (1891): the condition of labour
//
// Standalone module: the const is what the bake pipeline (canon_exemplars.py) evals
// via Node; the guarded window assignment exposes it to the frontend Canon-exemplar UI.

const CANON_SAMPLES = {
  nativity: `THE NATIVITY OF OUR LORD AND THE ADORATION OF THE MAGI

And it came to pass, that in those days there went out a decree from Caesar Augustus, that the whole world should be enrolled. This enrolling was first made by Cyrinus, the governor of Syria. And all went to be enrolled, every one into his own city. And Joseph also went up from Galilee, out of the city of Nazareth, into Judea, to the city of David, which is called Bethlehem: because he was of the house and family of David, to be enrolled with Mary his espoused wife, who was with child.

And it came to pass, that when they were there, her days were accomplished, that she should be delivered. And she brought forth her firstborn son, and wrapped him up in swaddling clothes, and laid him in a manger; because there was no room for them in the inn.

And there were in the same country shepherds watching, and keeping the night watches over their flock. And behold an angel of the Lord stood by them, and the brightness of God shone round about them; and they feared with a great fear. And the angel said to them: Fear not; for, behold, I bring you good tidings of great joy, that shall be to all the people: For, this day, is born to you a Saviour, who is Christ the Lord, in the city of David.

Now when Jesus was born in Bethlehem of Juda, in the days of king Herod, behold, there came wise men from the east to Jerusalem, saying: Where is he that is born king of the Jews? For we have seen his star in the east, and are come to adore him. And entering into the house, they found the child with Mary his mother, and falling down they adored him: and opening their treasures, they offered him gifts; gold, frankincense, and myrrh.`,

  sacraments: `THE SEVEN SACRAMENTS AND THE GRACE THEY CONFER

A sacrament is an outward sign instituted by Christ to give grace. The sacraments of the New Law are seven: Baptism, Confirmation, the Holy Eucharist, Penance, Extreme Unction, Holy Orders, and Matrimony.

Baptism is the sacrament that gives our souls the new life of sanctifying grace, by which we become children of God and heirs of heaven, and by which original sin is remitted.

Confirmation is the sacrament through which we receive the Holy Ghost to make us strong and perfect Christians and soldiers of Jesus Christ. The bishop administers Confirmation by the imposition of hands, the anointing with holy chrism, and prayer.

The Holy Eucharist is the sacrament which contains, under the appearances of bread and wine, the body and blood, soul and divinity, of our Lord Jesus Christ.

Penance is the sacrament by which the sins committed after Baptism are forgiven through the absolution of the priest. To receive it worthily we must examine our conscience, be sorry for our sins, have a firm purpose of amendment, confess our sins, and be willing to perform the penance enjoined.

Extreme Unction is the sacrament which, through the anointing with holy oil and the prayer of the priest, gives health and strength to the soul, and sometimes to the body, in dangerous illness.

Holy Orders is the sacrament by which bishops, priests, and other ministers of the Church are ordained and receive the power and grace to perform their sacred duties.

Matrimony is the sacrament that unites a Christian man and woman in lawful marriage. Baptism, Confirmation, and Holy Orders can be received only once, because each imprints on the soul a spiritual mark, called a character, which lasts for ever.`,

  trent_eucharist: `THE COUNCIL OF TRENT — DECREE CONCERNING THE MOST HOLY SACRAMENT OF THE EUCHARIST (SESSION THE THIRTEENTH)

The holy, oecumenical and general Synod of Trent, lawfully assembled in the Holy Ghost, declares, teaches, and defines concerning the most holy sacrament of the Eucharist.

In the first place, the holy Synod teaches, and openly and simply professes, that, in the august sacrament of the holy Eucharist, after the consecration of the bread and wine, our Lord Jesus Christ, true God and true man, is truly, really, and substantially contained under the species of those sensible things.

And because that Christ our Redeemer declared that which He offered under the species of bread to be truly His own body, therefore has it ever been a firm belief in the Church of God, that by the consecration of the bread and of the wine a conversion is made of the whole substance of the bread into the substance of the body of Christ our Lord, and of the whole substance of the wine into the substance of His blood; which conversion is, by the holy Catholic Church, suitably and properly called Transubstantiation.

Wherefore it is most true that as much is contained under either species as under both. For Christ whole and entire is under the species of bread, and under any part whatsoever of that species; likewise the whole Christ is under the species of wine, and under the parts thereof.

CANON I. If any one denieth, that, in the sacrament of the most holy Eucharist, are contained truly, really, and substantially, the body and blood together with the soul and divinity of our Lord Jesus Christ, and consequently the whole Christ; but saith that He is only therein as in a sign, or in figure, or virtue: let him be anathema.`,

  rerum_novarum: `RERUM NOVARUM — ON THE CONDITION OF LABOUR (POPE LEO XIII, 1891)

That the spirit of revolutionary change which has long been disturbing the nations of the world should have passed beyond the sphere of politics and made its influence felt in the cognate sphere of practical economics is not surprising. It is the Church that insists, on the authority of the Gospel, upon those teachings whereby the conflict can be brought to an end, or rendered at least far less bitter.

The great mistake made in regard to the matter now under consideration is to take up with the notion that class is naturally hostile to class, and that the wealthy and the working men are intended by nature to live in mutual conflict. So irrational and so false is this view that the direct contrary is the truth.

Every man has by nature the right to possess property as his own. To labour is to exert oneself for the sake of procuring what is necessary for the various purposes of life, and chief of all for self-preservation. The first and most fundamental principle, therefore, if one would undertake to alleviate the condition of the masses, must be the inviolability of private property.

Religion teaches the working man and the artisan to carry out honestly and well all equitable agreements freely made, never to injure the property nor to outrage the person of an employer. And the wealthy owner and the employer: their great and principal obligation is to give every one what is just. Neither justice nor humanity can countenance the exaction of so much labour as to stupefy the mind and wear out the body. It is neither justice nor mercy to grind men down with excessive toil so as to blunt their intellects and wear out their strength.`,
};

if (typeof window !== 'undefined') {
  window.CANON_SAMPLES = CANON_SAMPLES;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CANON_SAMPLES;
}
